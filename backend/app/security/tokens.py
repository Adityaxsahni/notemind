import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
_ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": issued_at,
        "exp": issued_at + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, get_settings().secret_key.get_secret_value(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key.get_secret_value(),
            algorithms=[_ALGORITHM],  # pinned: never trust the token's own "alg" header
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError:
        return None
    if payload["type"] != "access":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except ValueError:
        return None


def new_opaque_token() -> str:
    """256 bits of randomness, for refresh tokens and invite links."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Opaque tokens are stored hashed, so a database leak doesn't leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()
