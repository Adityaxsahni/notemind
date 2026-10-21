"""Security hardening: bot checks, CORS, rate limits, auth on every route, input hygiene,
error handling, analytics privacy, admin access and the audit trail."""

import logging
import time

import httpx
import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from app.config import get_settings
from app.deps import get_current_user
from app.main import app
from app.models import AnalyticsEvent, AuditLog
from app.security import bot
from tests.conftest import GOOD_PASSWORD, human, signup

# --- bot checks ----------------------------------------------------------------------------


def signup_body(client, **overrides):
    return {**human(client), "email": "a@x.com", "password": GOOD_PASSWORD, **overrides}


@pytest.mark.parametrize(
    "overrides",
    [
        {"form_token": None},  # posted straight to the API, no form loaded
        {"form_token": "123.abc"},  # forged
        {"website": "http://spam.example"},  # honeypot filled
    ],
)
def test_bot_signups_are_rejected_without_saying_why(make_client, overrides):
    client = make_client()
    response = client.post("/auth/signup", json=signup_body(client, **overrides))
    assert response.status_code == 400
    assert "person" in response.json()["detail"]
    assert client.get("/me").status_code == 401


def test_submitting_faster_than_a_person_is_rejected(make_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "bot_min_fill_seconds", 3.0)
    client = make_client()
    assert client.post("/auth/signup", json=signup_body(client)).status_code == 400
    old = bot.issue_form_token(now=time.time() - 4)
    assert client.post("/auth/signup", json=signup_body(client, form_token=old)).status_code == 201


def test_expired_form_token_is_rejected(make_client):
    client = make_client()
    stale = bot.issue_form_token(now=time.time() - 3 * 3600)
    assert (
        client.post("/auth/signup", json=signup_body(client, form_token=stale)).status_code == 400
    )


def test_login_has_the_same_bot_checks(make_client):
    signup(make_client(), "a@x.com")
    client = make_client()
    body = {"email": "a@x.com", "password": GOOD_PASSWORD, "website": "x", "form_token": None}
    assert client.post("/auth/login", json=body).status_code == 400


class FakeTurnstile:
    def __init__(self, success):
        self.success, self.calls = success, []

    def __call__(self, url, data, timeout):
        self.calls.append(data)
        return httpx.Response(200, json={"success": self.success})


@pytest.mark.parametrize(("success", "code"), [(True, 201), (False, 400)])
def test_captcha_is_verified_when_configured(make_client, monkeypatch, success, code):
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "turnstile_secret_key", SecretStr("turnstile-test"))
    fake = FakeTurnstile(success)
    monkeypatch.setattr(bot.httpx, "post", fake)
    client = make_client()
    response = client.post("/auth/signup", json=signup_body(client, captcha_token="tok"))
    assert response.status_code == code
    assert fake.calls[0]["response"] == "tok"


def test_missing_captcha_is_rejected_when_configured(make_client, monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "turnstile_secret_key", SecretStr("turnstile-test"))
    client = make_client()
    assert client.post("/auth/signup", json=signup_body(client)).status_code == 400


def test_captcha_outage_fails_closed(make_client, monkeypatch):
    from pydantic import SecretStr

    def down(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(get_settings(), "turnstile_secret_key", SecretStr("turnstile-test"))
    monkeypatch.setattr(bot.httpx, "post", down)
    client = make_client()
    response = client.post("/auth/signup", json=signup_body(client, captcha_token="t"))
    assert response.status_code == 400


# --- CORS, rate limits, trusting the client --------------------------------------------------


def test_cors_is_off_so_other_sites_get_no_access(make_client):
    response = make_client().options(
        "/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_cors_is_refused_by_config():
    from app.config import Settings

    with pytest.raises(ValueError, match="exact origins"):
        Settings(cors_origins=["*"])


def test_global_rate_limit_covers_every_route_but_health(make_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "global_rate_limit_per_minute", 3)
    client = make_client()
    codes = [client.get("/me").status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]
    assert client.get("/health").status_code == 200


def test_spoofed_forwarded_for_header_does_not_dodge_ip_limits(make_client):
    # Only the trusted proxy's X-Forwarded-For is honoured (uvicorn --forwarded-allow-ips);
    # a client making up its own address per request still hits the same limit.
    client = make_client()
    codes = [
        client.post(
            "/auth/signup",
            json=signup_body(client, email=f"u{i}@x.com"),
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(21)
    ]
    assert codes[:20] == [201] * 20
    assert codes[20] == 429


PUBLIC_ROUTES = {
    "/health",
    "/auth/form-token",
    "/auth/signup",
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/analytics/event",
    "/telemetry/errors",
}


def _requires_login(dependant) -> bool:
    return any(d.call is get_current_user or _requires_login(d) for d in dependant.dependencies)


def _api_routes(routes):
    """Every endpoint, including those inside included routers (which FastAPI wraps)."""
    for route in routes:
        if hasattr(route, "effective_candidates"):
            yield from _api_routes(route.effective_candidates())
        elif isinstance(route, APIRoute) or hasattr(route, "dependant"):
            yield route


def test_every_api_route_requires_login_unless_explicitly_public():
    routes = list(_api_routes(app.routes))
    assert len(routes) > 30
    unprotected = {r.path for r in routes if not _requires_login(r.dependant)}
    assert unprotected == PUBLIC_ROUTES, f"new public route? {unprotected ^ PUBLIC_ROUTES}"


# --- input and errors --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["DBMS\x00", "Notes\x1b[31m", "Evil‮name"])
def test_control_characters_are_rejected(make_client, name):
    client = make_client()
    signup(client, "a@x.com")
    assert client.post("/collections", json={"name": name}).status_code == 422


def test_unhandled_errors_return_a_generic_500_with_request_id(make_client, caplog):
    def boom():
        raise RuntimeError("secret internals: password=hunter2")  # pragma: allowlist secret

    app.add_api_route("/__boom", boom)
    try:
        with caplog.at_level(logging.ERROR):
            response = make_client().get("/__boom")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]
    assert response.status_code == 500
    assert "secret internals" not in response.text
    assert "Traceback" not in response.text
    request_id = response.json()["request_id"]
    assert response.headers["X-Request-ID"] == request_id
    assert request_id in caplog.text  # the log line an operator searches for


def test_responses_carry_security_headers(make_client):
    response = make_client().get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in response.headers


# --- analytics and error reports ---------------------------------------------------------------


def test_page_views_store_no_identifiers(make_client, db):
    client = make_client()
    response = client.post(
        "/analytics/event",
        json={
            "path": "/c/3f2a6b1e-1111-4222-8333-944455556666?tab=quiz",
            "referrer": "https://www.google.com/search?q=notemind",
        },
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)"},
    )
    assert response.status_code == 204
    with db() as s:
        [event] = s.scalars(select(AnalyticsEvent)).all()
    assert event.path == "/c/:id"
    assert event.referrer_host == "www.google.com"
    assert event.device == "mobile"


@pytest.mark.parametrize("header", [{"DNT": "1"}, {"Sec-GPC": "1"}])
def test_do_not_track_is_honoured(make_client, db, header):
    assert (
        make_client().post("/analytics/event", json={"path": "/"}, headers=header).status_code
        == 204
    )
    with db() as s:
        assert s.scalars(select(AnalyticsEvent)).all() == []


def test_visitors_cannot_read_analytics_back(make_client):
    client = make_client()
    signup(client, "a@x.com")
    assert client.get("/admin/analytics").status_code == 403


def test_client_errors_are_logged_scrubbed(make_client, caplog):
    with caplog.at_level(logging.ERROR, logger="app.api.telemetry"):
        response = make_client().post(
            "/telemetry/errors",
            json={
                "message": "TypeError for alice@x.com in 3f2a6b1e-1111-4222-8333-944455556666",
                "path": "/c/3f2a6b1e-1111-4222-8333-944455556666",
                "stack": "at a\nat b",
            },
        )
    assert response.status_code == 204
    assert "client_error path=/c/:id" in caplog.text
    assert "alice@x.com" not in caplog.text
    assert "<email>" in caplog.text


# --- admin & audit trail -----------------------------------------------------------------------


@pytest.fixture
def admin(make_client, db):
    client = make_client()
    signup(client, "root@x.com")
    with db() as s:
        s.execute(text("UPDATE users SET is_admin = true WHERE email = 'root@x.com'"))
        s.commit()
    return client


def test_admin_sees_analytics_and_every_admin_view_is_audited(admin, make_client, db):
    make_client().post("/analytics/event", json={"path": "/privacy"})
    stats = admin.get("/admin/analytics?days=7").json()
    assert stats["total_views"] == 1
    assert stats["top_pages"] == [{"key": "/privacy", "views": 1}]
    log = admin.get("/admin/audit-log").json()
    assert [e["action"] for e in log][:1] == ["admin.view_analytics"]
    with db() as s:
        actions = s.scalars(select(AuditLog.action)).all()
    assert {"admin.view_analytics", "admin.view_audit_log"} <= set(actions)


def test_sensitive_actions_are_audited(make_client, db):
    alice = make_client()
    alice_id = signup(alice, "alice@x.com")["id"]
    cid = alice.post("/collections", json={"name": "DBMS"}).json()["id"]
    invite = alice.post(f"/collections/{cid}/invites", json={}).json()
    alice.delete(f"/collections/{cid}/invites/{invite['id']}")
    alice.delete(f"/collections/{cid}")
    alice.request("DELETE", "/me", json={"password": GOOD_PASSWORD})
    with db() as s:
        rows = s.execute(select(AuditLog.action, AuditLog.actor_id)).all()
    assert [a for a, _ in rows] == [
        "invite.created",
        "invite.revoked",
        "collection.deleted",
        "account.deleted",
    ]
    assert {str(actor) for _, actor in rows} == {alice_id}
