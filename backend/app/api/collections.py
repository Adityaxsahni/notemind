import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app import audit
from app.authz import Action, assert_can_access
from app.deps import CurrentUser, SessionDep
from app.models import Collection, CollectionMember, Document, Role, User
from app.schemas import CollectionIn, CollectionOut, MemberOut
from app.storage import StorageDep

router = APIRouter(prefix="/collections", tags=["collections"])

MAX_COLLECTIONS_PER_USER = 50


def collection_out(collection: Collection, role: Role) -> CollectionOut:
    return CollectionOut(
        id=collection.id, name=collection.name, role=role, created_at=collection.created_at
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CollectionOut)
def create_collection(body: CollectionIn, user: CurrentUser, session: SessionDep) -> CollectionOut:
    owned = session.scalar(
        select(func.count()).select_from(Collection).where(Collection.owner_id == user.id)
    )
    if owned >= MAX_COLLECTIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You can have at most {MAX_COLLECTIONS_PER_USER} collections",
        )
    collection = Collection(owner_id=user.id, name=body.name)
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection_out(collection, Role.OWNER)


@router.get("", response_model=list[CollectionOut])
def list_collections(user: CurrentUser, session: SessionDep) -> list[CollectionOut]:
    owned = session.scalars(select(Collection).where(Collection.owner_id == user.id)).all()
    shared = session.execute(
        select(Collection, CollectionMember.role)
        .join(CollectionMember, CollectionMember.collection_id == Collection.id)
        .where(CollectionMember.user_id == user.id)
    ).all()
    items = [collection_out(c, Role.OWNER) for c in owned] + [
        collection_out(c, role) for c, role in shared
    ]
    return sorted(items, key=lambda c: c.created_at, reverse=True)


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(
    collection_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CollectionOut:
    access = assert_can_access(session, user, collection_id, Action.READ)
    return collection_out(access.collection, access.role)


@router.patch("/{collection_id}", response_model=CollectionOut)
def rename_collection(
    collection_id: uuid.UUID, body: CollectionIn, user: CurrentUser, session: SessionDep
) -> CollectionOut:
    access = assert_can_access(session, user, collection_id, Action.MANAGE)
    access.collection.name = body.name
    session.commit()
    return collection_out(access.collection, access.role)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    request: Request,
) -> None:
    access = assert_can_access(session, user, collection_id, Action.MANAGE)
    keys = session.scalars(
        select(Document.storage_key).where(Document.collection_id == collection_id)
    ).all()
    session.delete(access.collection)  # documents and pages cascade in the database
    audit.record(
        session,
        "collection.deleted",
        actor_id=user.id,
        request=request,
        target_type="collection",
        target_id=collection_id,
        details={"documents": len(keys)},
    )
    session.commit()
    for key in keys:  # files on disk don't cascade; remove them explicitly
        storage.delete(key)


@router.get("/{collection_id}/members", response_model=list[MemberOut])
def list_members(
    collection_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[MemberOut]:
    # Owner-only: viewers shouldn't be able to harvest classmates' email addresses.
    assert_can_access(session, user, collection_id, Action.MANAGE)
    rows = session.execute(
        select(CollectionMember, User.email)
        .join(User, User.id == CollectionMember.user_id)
        .where(CollectionMember.collection_id == collection_id)
        .order_by(CollectionMember.created_at)
    ).all()
    return [
        MemberOut(user_id=m.user_id, email=email, role=m.role, joined_at=m.created_at)
        for m, email in rows
    ]


@router.delete("/{collection_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    collection_id: uuid.UUID,
    member_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> None:
    """Owner removes a member, or a member leaves (member_id == own id)."""
    if member_id == user.id:
        access = assert_can_access(session, user, collection_id, Action.READ)
        if access.role == Role.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The owner can't leave; delete the collection instead",
            )
    else:
        assert_can_access(session, user, collection_id, Action.MANAGE)
    member = session.get(CollectionMember, (collection_id, member_id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    session.delete(member)
    audit.record(
        session,
        "member.left" if member_id == user.id else "member.removed",
        actor_id=user.id,
        request=request,
        target_type="collection",
        target_id=collection_id,
        details={"member_id": str(member_id)},
    )
    session.commit()
