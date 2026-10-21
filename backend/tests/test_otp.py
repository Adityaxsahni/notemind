"""Two-step sign-in: password, then a 6-digit code sent by email."""

import re

import pytest

from app.config import get_settings
from app.mail import get_mailer
from app.main import app
from app.security import otp
from tests.conftest import GOOD_PASSWORD, human


class FakeMailer:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    @property
    def last_code(self) -> str:
        return re.search(r"\b(\d{6})\b", self.sent[-1][2]).group(1)


@pytest.fixture
def mailer(monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_required", True)
    fake = FakeMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mailer, None)


def start_signup(client, email="alice@x.com"):
    response = client.post(
        "/auth/signup", json={"email": email, "password": GOOD_PASSWORD, **human(client)}
    )
    assert response.status_code == 202, response.text
    return response.json()


def start_login(client, email="alice@x.com", password=GOOD_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password, **human(client)})


def verify(client, challenge_id, code):
    return client.post("/auth/otp/verify", json={"challenge_id": challenge_id, "code": code})


def test_signup_emails_a_code_and_signs_in_only_after_it(make_client, mailer):
    client = make_client()
    challenge = start_signup(client)
    assert challenge["otp_required"] is True
    assert challenge["email_hint"] == "a***@x.com"
    assert challenge["dev_code"] is None  # never on screen outside local development
    assert "access_token" not in client.cookies
    assert client.get("/me").status_code == 401

    [(to, subject, body)] = mailer.sent
    assert to == "alice@x.com"
    assert mailer.last_code in subject and "10 minutes" in body

    response = verify(client, challenge["challenge_id"], mailer.last_code)
    assert response.status_code == 200, response.text
    assert client.get("/me").json()["email"] == "alice@x.com"


def test_login_needs_password_then_code(make_client, mailer):
    client = make_client()
    verify(client, start_signup(client)["challenge_id"], mailer.last_code)
    client.post("/auth/logout")

    other = make_client()
    wrong = "wrong-password-123"  # pragma: allowlist secret
    assert start_login(other, password=wrong).status_code == 401
    assert len(mailer.sent) == 1  # no code for a wrong password

    response = start_login(other)
    assert response.status_code == 202
    assert other.get("/me").status_code == 401
    assert verify(other, response.json()["challenge_id"], mailer.last_code).status_code == 200
    assert other.get("/me").status_code == 200


def test_wrong_code_expired_challenge_and_replay_are_refused(make_client, mailer):
    client = make_client()
    challenge_id = start_signup(client)["challenge_id"]
    code = mailer.last_code
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    assert verify(client, challenge_id, wrong).status_code == 400
    assert verify(client, challenge_id, code).status_code == 200
    assert verify(client, challenge_id, code).status_code == 400  # single use
    assert verify(client, "x" * 32, code).status_code == 400  # unknown challenge


def test_five_wrong_guesses_end_the_challenge(make_client, mailer):
    client = make_client()
    challenge_id = start_signup(client)["challenge_id"]
    code = mailer.last_code
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for _ in range(otp.MAX_ATTEMPTS):
        assert verify(client, challenge_id, wrong).status_code == 400
    assert verify(client, challenge_id, code).status_code == 400  # even the right one, now


def test_resend_replaces_the_code_and_is_limited(make_client, mailer):
    client = make_client()
    challenge_id = start_signup(client)["challenge_id"]
    first = mailer.last_code
    for _ in range(otp.MAX_SENDS - 1):
        response = client.post("/auth/otp/resend", json={"challenge_id": challenge_id})
        assert response.status_code == 200
    assert client.post("/auth/otp/resend", json={"challenge_id": challenge_id}).status_code == 429
    latest = mailer.last_code
    if latest != first:
        assert verify(client, challenge_id, first).status_code == 400
    assert verify(client, challenge_id, latest).status_code == 200


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
def test_malformed_codes_are_rejected(make_client, mailer, code):
    client = make_client()
    challenge_id = start_signup(client)["challenge_id"]
    assert verify(client, challenge_id, code).status_code == 422


def test_code_shown_on_screen_only_for_local_development_without_smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "environment", "local")
    assert settings.show_otp_on_screen
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert not settings.show_otp_on_screen
    monkeypatch.setattr(settings, "smtp_host", None)
    for environment in ("test", "staging", "production"):
        monkeypatch.setattr(settings, "environment", environment)
        assert not settings.show_otp_on_screen


def test_deployments_must_configure_email(monkeypatch):
    from app.config import Settings

    with pytest.raises(ValueError, match="SMTP_HOST"):
        Settings(environment="production", secret_key="s" * 40, otp_required=True, smtp_host=None)
    Settings(environment="production", secret_key="s" * 40, smtp_host="smtp.example.com")


def test_only_a_hash_of_the_code_is_stored(make_client, mailer, redis):
    client = make_client()
    start_signup(client)
    [key] = redis.keys("otp:*")
    stored = redis.hgetall(key)
    assert mailer.last_code.encode() not in b"".join(stored.values())
