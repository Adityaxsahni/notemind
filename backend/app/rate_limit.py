import hashlib

from fastapi import HTTPException, Request, status
from redis import Redis


def client_ip(request: Request) -> str:
    # Behind a proxy, run uvicorn with --proxy-headers and trusted --forwarded-allow-ips.
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
