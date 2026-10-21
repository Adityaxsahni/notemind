from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from redis import Redis
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session, set_rls_user
from app.embeddings import Embedder, get_embedder
from app.llm.gateway import LLMGateway
from app.llm.providers import LLMProvider, get_llm_provider
from app.models import User
from app.rag.reranker import Reranker, get_reranker
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
    set_rls_user(session, user.id)  # row-level security: this request sees only their rows
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# Models load once per process; tests override these with fakes.
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
RerankerDep = Annotated[Reranker, Depends(get_reranker)]


def get_llm_gateway(
    redis: RedisDep, provider: Annotated[LLMProvider | None, Depends(get_llm_provider)]
) -> LLMGateway:
    settings = get_settings()
    return LLMGateway(
        provider,
        redis,
        user_daily_budget=settings.llm_user_daily_token_budget,
        global_daily_budget=settings.llm_global_daily_token_budget,
    )


LLMGatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]
