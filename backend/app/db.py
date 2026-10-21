import uuid
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.rls import APP_ROLE


class Base(DeclarativeBase):
    pass


_SET_USER = text("SELECT set_config('app.user_id', :uid, true)")


def use_app_role(engine: Engine) -> Engine:
    """Run every connection of `engine` as the restricted role that row-level security
    policies apply to (see app/rls.py). Migrations and admin scripts use the owner instead."""

    @event.listens_for(engine, "connect")
    def _set_role(dbapi_connection, _record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {APP_ROLE}")  # a constant, not user input
        dbapi_connection.commit()  # outside a committed transaction the SET would roll back

    return engine


@event.listens_for(Session, "after_begin")
def _apply_rls_user(session: Session, _transaction, connection) -> None:
    # Transaction-scoped (is_local=true): it can't leak to the next user of a pooled connection.
    connection.execute(_SET_USER, {"uid": session.info.get("rls_user_id", "")})


def set_rls_user(session: Session, user_id: uuid.UUID) -> None:
    """Make this session act as `user_id` for row-level security, now and after commits."""
    session.info["rls_user_id"] = str(user_id)
    if session.in_transaction():
        session.execute(_SET_USER, {"uid": str(user_id)})


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return use_app_role(
        create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
    )


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
