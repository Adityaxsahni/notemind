from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from redis import Redis
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.redis_client import get_redis
from app.security.tokens import decode_access_token

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

SessionDep = Annotated[Session, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def get_current_user(
    session: SessionDep,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    user_id = decode_access_token(access_token) if access_token else None
    # Re-load from the DB so deleted accounts lose access immediately, not at token expiry.
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
