import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis import Redis

from app.config import get_settings
from app.redis_client import get_redis


def client_ip(request: Request) -> str:
    """The visitor's address. Behind the Next.js proxy, uvicorn's --proxy-headers rewrites
    request.client from X-Forwarded-For, trusting it only from FORWARDED_ALLOW_IPS (the
    proxy's network). Without that, every visitor would share the proxy's address."""
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    redis: Redis, scope: str, identifier: str, *, limit: int, window_seconds: int
) -> None:
    """Fixed-window limiter. Raises 429 once `limit` hits occur within the window.

    Identifiers (which may contain emails) are hashed so Redis never stores them in clear.
    """
    digest = hashlib.sha256(identifier.encode()).hexdigest()[:32]
    key = f"rl:{scope}:{digest}"
    redis.set(key, 0, ex=window_seconds, nx=True)
    if redis.incr(key) > limit:
        retry_after = redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after if retry_after > 0 else window_seconds)},
        )


def global_rate_limit(request: Request, redis: Annotated[Redis, Depends(get_redis)]) -> None:
    """App-wide dependency: a generous per-IP ceiling on every route except the health check."""
    if request.url.path == "/health":
        return
    enforce_rate_limit(
        redis,
        "global",
        client_ip(request),
        limit=get_settings().global_rate_limit_per_minute,
        window_seconds=60,
    )
