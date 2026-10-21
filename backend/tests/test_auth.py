import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import RefreshToken, User
from app.security.tokens import create_access_token
from tests.conftest import GOOD_PASSWORD, human, signup

WRONG_PASSWORD = "definitely-not-it-99"  # pragma: allowlist secret


def _set_cookie_headers(response):
    return response.headers.get_list("set-cookie")


def test_signup_sets_hardened_cookies_and_hides_hash(client):
    response = client.post(
        "/auth/signup", json={**human(client), "email": "a@x.com", "password": GOOD_PASSWORD}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@x.com"
    assert "password_hash" not in body and "password" not in body

    cookies = _set_cookie_headers(response)
    access = next(c for c in cookies if c.startswith("access_token="))
    refresh = next(c for c in cookies if c.startswith("refresh_token="))
    for cookie in (access, refresh):
        lowered = cookie.lower()
        assert "httponly" in lowered
        assert "secure" in lowered
        assert "samesite=strict" in lowered
    assert "path=/auth" in refresh.lower()
    # The UI hint is readable by scripts, so it must never carry anything secret.
    hint = next(c for c in cookies if c.startswith("signed_in="))
    assert hint.startswith("signed_in=1;")
    assert "httponly" not in hint.lower()


def test_password_stored_with_argon2id(client, db):
    signup(client, "a@x.com")
    with db() as session:
        user = session.scalar(select(User).where(User.email == "a@x.com"))
    assert user.password_hash.startswith("$argon2id$")


def test_duplicate_email_is_case_insensitive(client):
    signup(client, "a@x.com")
    response = client.post(
        "/auth/signup", json={**human(client), "email": "A@X.com", "password": GOOD_PASSWORD}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "password",
    [
        "short",  # too short
        "password123",  # common
        "aaaaaaaaaaaa",  # repetitive
        "alice-is-great-2024",  # contains email local part
        "x" * 129,  # too long (bounds hashing cost)
    ],
)
def test_weak_passwords_rejected(client, password):
    response = client.post(
        "/auth/signup", json={**human(client), "email": "alice@x.com", "password": password}
    )
    assert response.status_code == 422


def test_validation_errors_do_not_echo_password(client):
    secret = "password123"  # pragma: allowlist secret
    response = client.post(
        "/auth/signup", json={**human(client), "email": "alice@x.com", "password": secret}
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_login_errors_are_identical_for_unknown_email_and_wrong_password(make_client):
    signup(make_client(), "a@x.com")
    client = make_client()
    wrong_pw = client.post(
        "/auth/login", json={**human(client), "email": "a@x.com", "password": WRONG_PASSWORD}
    )
    no_user = client.post(
        "/auth/login", json={**human(client), "email": "b@x.com", "password": WRONG_PASSWORD}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_login_success_then_me(make_client):
    signup(make_client(), "a@x.com")
    client = make_client()
    response = client.post(
        "/auth/login", json={**human(client), "email": "A@x.com", "password": GOOD_PASSWORD}
    )
    assert response.status_code == 200
    assert client.get("/me").json()["email"] == "a@x.com"


def test_login_is_rate_limited(make_client):
    signup(make_client(), "a@x.com")
    client = make_client()
    codes = [
        client.post(
            "/auth/login", json={**human(client), "email": "a@x.com", "password": WRONG_PASSWORD}
        ).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
    # Even the correct password is refused while limited: brute force can't "get lucky".
    response = client.post(
        "/auth/login", json={**human(client), "email": "a@x.com", "password": GOOD_PASSWORD}
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_me_requires_authentication(make_client):
    assert make_client().get("/me").status_code == 401


def test_tampered_and_expired_tokens_rejected(make_client):
    user = signup(make_client(), "a@x.com")
    user_id = uuid.UUID(user["id"])

    expired = create_access_token(user_id, now=datetime.now(UTC) - timedelta(hours=1))
    valid = create_access_token(user_id)
    tampered = valid[:-4] + ("AAAA" if not valid.endswith("AAAA") else "BBBB")

    for token in (expired, tampered, "not-a-jwt"):
        response = make_client().get("/me", headers={"Cookie": f"access_token={token}"})
        assert response.status_code == 401


def test_alg_none_token_rejected(make_client):
    import jwt

    user = signup(make_client(), "a@x.com")
    forged = jwt.encode(
        {
            "sub": user["id"],
            "type": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        key=None,
        algorithm="none",
    )
    response = make_client().get("/me", headers={"Cookie": f"access_token={forged}"})
    assert response.status_code == 401


def test_refresh_rotates_token(client):
    signup(client, "a@x.com")
    old = client.cookies.get("refresh_token")
    response = client.post("/auth/refresh")
    assert response.status_code == 204
    new = client.cookies.get("refresh_token")
    assert new and new != old
    assert client.get("/me").status_code == 200


def test_refresh_token_reuse_revokes_whole_family(make_client, db):
    victim = make_client()
    signup(victim, "a@x.com")
    stolen = victim.cookies.get("refresh_token")

    # Victim refreshes normally, so the stolen token is now "used".
    assert victim.post("/auth/refresh").status_code == 204
    victims_current = victim.cookies.get("refresh_token")

    # Attacker replays the stolen token: rejected, and the alarm revokes the family.
    attacker = make_client()
    replay = attacker.post("/auth/refresh", headers={"Cookie": f"refresh_token={stolen}"})
    assert replay.status_code == 401

    # The victim's current token is revoked too, forcing a fresh login.
    retry = make_client().post(
        "/auth/refresh", headers={"Cookie": f"refresh_token={victims_current}"}
    )
    assert retry.status_code == 401
    with db() as session:
        tokens = session.scalars(select(RefreshToken)).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)


def test_logout_revokes_refresh_token(client):
    signup(client, "a@x.com")
    refresh_token = client.cookies.get("refresh_token")
    assert client.post("/auth/logout").status_code == 204
    other = client.post("/auth/refresh", headers={"Cookie": f"refresh_token={refresh_token}"})
    assert other.status_code == 401
