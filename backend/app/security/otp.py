"""One-time codes: the second step of signing in (password, then a 6-digit code by email).

A challenge lives in Redis for 10 minutes under a random id the browser holds. Only an HMAC
of the code is stored, so a Redis dump reveals nothing usable. Five wrong guesses end the
challenge (10^6 codes, 5 tries: a 1 in 200,000 chance), and at most three codes are sent.
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from redis import Redis

from app.config import get_settings

CODE_TTL_SECONDS = 600
MAX_ATTEMPTS = 5
MAX_SENDS = 3

_INVALID = "That code is wrong or has expired. Check the latest email, or request a new code."


@dataclass(frozen=True)
class Challenge:
    id: str
    user_id: uuid.UUID
    code: str  # sent to the user, never stored


def _key(challenge_id: str) -> str:
    return f"otp:{hashlib.sha256(challenge_id.encode()).hexdigest()[:32]}"


def _digest(challenge_id: str, code: str) -> str:
    secret = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(secret, f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def start(redis: Redis, user_id: uuid.UUID) -> Challenge:
    challenge_id = secrets.token_urlsafe(24)
    code = _new_code()
    key = _key(challenge_id)
    pipe = redis.pipeline()
    pipe.hset(
        key,
        mapping={
            "user_id": str(user_id),
            "code": _digest(challenge_id, code),
            "attempts": 0,
            "sends": 1,
        },
    )
    pipe.expire(key, CODE_TTL_SECONDS)
    pipe.execute()
    return Challenge(challenge_id, user_id, code)


def resend(redis: Redis, challenge_id: str) -> Challenge:
    """A fresh code for an open challenge; the previous code stops working."""
    key = _key(challenge_id)
    user_id = redis.hget(key, "user_id")
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID)
    if redis.hincrby(key, "sends", 1) > MAX_SENDS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many codes requested. Start signing in again in a few minutes.",
        )
    code = _new_code()
    pipe = redis.pipeline()
    pipe.hset(key, mapping={"code": _digest(challenge_id, code), "attempts": 0})
    pipe.expire(key, CODE_TTL_SECONDS)
    pipe.execute()
    return Challenge(challenge_id, uuid.UUID(user_id.decode()), code)


def verify(redis: Redis, challenge_id: str, code: str) -> uuid.UUID:
    """The user id if the code is right; the challenge is then used up."""
    key = _key(challenge_id)
    stored = redis.hmget(key, "user_id", "code")
    if stored[0] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID)
    if redis.hincrby(key, "attempts", 1) > MAX_ATTEMPTS:
        redis.delete(key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID)
    if not hmac.compare_digest(stored[1].decode(), _digest(challenge_id, code)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID)
    # Single use: a second verify with the same code (replay) finds nothing.
    if not redis.delete(key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=_INVALID)
    return uuid.UUID(stored[0].decode())


def email_hint(email: str) -> str:
    """Like r***@gmail.com: enough to recognise the inbox, not to harvest the address."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"
