"""The single place that decides who may do what to a collection.

Every endpoint touching a collection (and later its documents, chunks, chats, quizzes)
must go through assert_can_access.
"""

import enum
import uuid
from typing import NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Collection, CollectionMember, Role, User


class Action(enum.StrEnum):
    READ = "read"  # view, search, ask questions, take quizzes
    WRITE = "write"  # upload and delete documents
    MANAGE = "manage"  # rename, delete, share, manage members


_PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(Action),
    Role.VIEWER: frozenset({Action.READ}),
}


class Access(NamedTuple):
    collection: Collection
    role: Role


def get_role(session: Session, user_id: uuid.UUID, collection: Collection) -> Role | None:
    if collection.owner_id == user_id:
        return Role.OWNER
    return session.scalar(
        select(CollectionMember.role).where(
            CollectionMember.collection_id == collection.id,
            CollectionMember.user_id == user_id,
        )
    )


def assert_can_access(
    session: Session, user: User, collection_id: uuid.UUID, action: Action
) -> Access:
    collection = session.get(Collection, collection_id)
    role = get_role(session, user.id, collection) if collection else None
    if collection is None or role is None:
        # 404, not 403: don't reveal that someone else's collection exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    if action not in _PERMISSIONS[role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to do that",
        )
    return Access(collection, role)
