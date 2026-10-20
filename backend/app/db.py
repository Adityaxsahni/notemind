from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def new_session() -> Session:
    """A session for code outside a request (background jobs). Caller must close it."""
    return _session_factory()()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = new_session()
    try:
        yield session
    finally:
        session.close()
