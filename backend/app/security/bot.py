"""Spam and bot checks for the public forms (sign up, log in).

Layers, cheapest first; any one failing rejects the request:
1. Honeypot: a form field humans never see. Simple bots fill every input.
2. Form token: a signed timestamp from GET /auth/form-token. It proves the page was loaded
   and how long ago, so scripts that post straight to the API, or submit a form faster than
   a person can type, are turned away. Not a secret: it raises the cost of naive bots, nothing
   more.
3. CAPTCHA (Cloudflare Turnstile) when TURNSTILE_SECRET_KEY is set: the real bot check.
Rate limits per IP and per account (app/rate_limit.py) sit underneath all of this.

The response never says which check failed, so it can't be used to tune a bot; the reason is
logged instead.
"""

import hashlib
import hmac
import logging
import time

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

_MAX_AGE_SECONDS = 2 * 3600
_TURNSTILE_VERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_REJECTED = "We couldn't verify you're a person. Refresh the page and try again."


def _sign(timestamp: str) -> str:
    key = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(key, f"form:{timestamp}".encode(), hashlib.sha256).hexdigest()[:32]


def issue_form_token(now: float | None = None) -> str:
    timestamp = str(int((now or time.time()) * 1000))
    return f"{timestamp}.{_sign(timestamp)}"


def _token_problem(token: str | None, now: float) -> str | None:
    if not token or token.count(".") != 1:
        return "missing_token"
    timestamp, signature = token.split(".")
    if not timestamp.isdigit() or not hmac.compare_digest(signature, _sign(timestamp)):
        return "bad_token"
    age = now - int(timestamp) / 1000
    if age > _MAX_AGE_SECONDS or age < -5:
        return "expired_token"
    if age < get_settings().bot_min_fill_seconds:
        return "too_fast"
    return None


def _turnstile_ok(captcha_token: str | None, ip: str) -> bool:
    secret = get_settings().turnstile_secret_key
    if secret is None:
        return True  # not configured: the other layers still apply
    if not captcha_token:
        return False
    try:
        result = httpx.post(
            _TURNSTILE_VERIFY,
            data={"secret": secret.get_secret_value(), "response": captcha_token, "remoteip": ip},
            timeout=5,
        ).json()
    except (httpx.HTTPError, ValueError):
        logger.error("turnstile verification unavailable")
        return False  # fail closed: a bot wave shouldn't get through during an outage
    return bool(result.get("success"))


def require_human(
    *, form: str, ip: str, form_token: str | None, honeypot: str, captcha_token: str | None
) -> None:
    """Raise 400 unless the submission looks like a person using our own form."""
    now = time.time()
    reason = (
        "honeypot"
        if honeypot
        else _token_problem(form_token, now)
        or (None if _turnstile_ok(captcha_token, ip) else "captcha")
    )
    if reason:
        logger.info("bot check failed form=%s reason=%s", form, reason)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_REJECTED)
