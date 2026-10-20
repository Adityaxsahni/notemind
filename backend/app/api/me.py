from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import or_, select

from app.api.auth import clear_auth_cookies
from app.deps import CurrentUser, RedisDep, SessionDep
from app.models import Collection, CollectionMember, Document, User
from app.rate_limit import enforce_rate_limit
from app.schemas import PasswordConfirmIn, UserOut
from app.security.passwords import verify_password
from app.storage import StorageDep

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def get_me(user: CurrentUser) -> User:
    return user


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: PasswordConfirmIn,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    storage: StorageDep,
) -> None:
    """Right to erasure (DPDP Act). Requires the password so a stolen session can't wipe data.

    Foreign keys cascade, so collections, documents, memberships, invites and sessions go with
    the user. Files on disk are deleted explicitly after the commit.
    """
    enforce_rate_limit(redis, "delete-me", str(user.id), limit=5, window_seconds=300)
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")
    keys = session.scalars(
        select(Document.storage_key)
        .join(Collection, Collection.id == Document.collection_id)
        .where(or_(Collection.owner_id == user.id, Document.uploaded_by == user.id))
    ).all()
    session.delete(user)
    session.commit()
    for key in keys:
        storage.delete(key)
    clear_auth_cookies(response)


@router.get("/export")
def export_me(user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    """Right to access (DPDP Act): everything we hold about the user, as JSON."""
    owned = session.scalars(select(Collection).where(Collection.owner_id == user.id)).all()
    shared = session.execute(
        select(Collection.id, Collection.name, CollectionMember.role, CollectionMember.created_at)
        .join(CollectionMember, CollectionMember.collection_id == Collection.id)
        .where(CollectionMember.user_id == user.id)
    ).all()
    return {
        "user": {"id": user.id, "email": user.email, "created_at": user.created_at},
        "collections_owned": [
            {"id": c.id, "name": c.name, "created_at": c.created_at} for c in owned
        ],
        "collections_shared_with_me": [
            {"id": cid, "name": name, "role": role, "joined_at": joined}
            for cid, name, role, joined in shared
        ],
    }
