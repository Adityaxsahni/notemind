import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.collections import collection_out
from app.authz import Action, assert_can_access
from app.deps import CurrentUser, RedisDep, SessionDep
from app.models import Collection, CollectionMember, InviteLink, Role
from app.rate_limit import enforce_rate_limit
from app.schemas import (
    CollectionOut,
    InviteAcceptIn,
    InviteCreatedOut,
    InviteCreateIn,
    InviteOut,
)
from app.security.tokens import hash_token, new_opaque_token

router = APIRouter(tags=["invites"])

MAX_ACTIVE_INVITES = 10


@router.post(
    "/collections/{collection_id}/invites",
    status_code=status.HTTP_201_CREATED,
    response_model=InviteCreatedOut,
)
def create_invite(
    collection_id: uuid.UUID, body: InviteCreateIn, user: CurrentUser, session: SessionDep
) -> InviteCreatedOut:
    assert_can_access(session, user, collection_id, Action.MANAGE)
    now = datetime.now(UTC)
    active = session.scalars(
        select(InviteLink.id).where(
            InviteLink.collection_id == collection_id,
            InviteLink.revoked_at.is_(None),
            InviteLink.expires_at > now,
        )
    ).all()
    if len(active) >= MAX_ACTIVE_INVITES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Too many active invite links; revoke one first",
        )
    token = new_opaque_token()
    invite = InviteLink(
        collection_id=collection_id,
        created_by=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=body.expires_in_days),
    )
    session.add(invite)
    session.commit()
    return InviteCreatedOut(id=invite.id, token=token, expires_at=invite.expires_at)


@router.get("/collections/{collection_id}/invites", response_model=list[InviteOut])
def list_invites(
    collection_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[InviteLink]:
    assert_can_access(session, user, collection_id, Action.MANAGE)
    return list(
        session.scalars(
            select(InviteLink)
            .where(
                InviteLink.collection_id == collection_id,
                InviteLink.revoked_at.is_(None),
                InviteLink.expires_at > datetime.now(UTC),
            )
            .order_by(InviteLink.created_at.desc())
        )
    )


@router.delete(
    "/collections/{collection_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_invite(
    collection_id: uuid.UUID, invite_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    assert_can_access(session, user, collection_id, Action.MANAGE)
    invite = session.get(InviteLink, invite_id)
    # Check the invite belongs to *this* collection, or an owner of one collection could
    # revoke invites of another by mixing IDs.
    if invite is None or invite.collection_id != collection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        session.commit()


@router.post("/invites/accept", response_model=CollectionOut)
def accept_invite(
    body: InviteAcceptIn, user: CurrentUser, session: SessionDep, redis: RedisDep
) -> CollectionOut:
    # Token goes in the body, not the URL, so it doesn't end up in proxy/access logs.
    enforce_rate_limit(redis, "invite-accept", str(user.id), limit=20, window_seconds=3600)
    invite = session.scalar(
        select(InviteLink).where(InviteLink.token_hash == hash_token(body.token))
    )
    if invite is None or invite.revoked_at is not None or invite.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite link is invalid or expired"
        )
    collection = session.get(Collection, invite.collection_id)
    if collection.owner_id == user.id:
        return collection_out(collection, Role.OWNER)
    if session.get(CollectionMember, (collection.id, user.id)) is None:
        session.add(
            CollectionMember(collection_id=collection.id, user_id=user.id, role=Role.VIEWER)
        )
        session.commit()
    return collection_out(collection, Role.VIEWER)
