import hashlib
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from app.authz import Action, assert_can_access
from app.config import get_settings
from app.deps import CurrentUser, RedisDep, SessionDep
from app.ingestion.queue import EnqueueDep
from app.ingestion.tasks import expire_stale, mark_failed
from app.ingestion.validation import UploadRejected, detect_kind, safe_display_name
from app.models import Document, DocumentKind
from app.rate_limit import enforce_rate_limit
from app.schemas import DocumentOut
from app.storage import StorageDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections/{collection_id}/documents", tags=["documents"])

_MEDIA_TYPES = {
    DocumentKind.PDF: "application/pdf",
    DocumentKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentKind.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _get_document(session: Session, collection_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    # Filter on BOTH ids: a document ID from another collection must not resolve here.
    document = session.scalar(
        select(Document).where(Document.id == document_id, Document.collection_id == collection_id)
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _too_large(limit: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=f"Files can be at most {limit // (1024 * 1024)} MB",
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut)
async def upload_document(
    collection_id: uuid.UUID,
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    user: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    storage: StorageDep,
    enqueue: EnqueueDep,
) -> Document:
    """Upload a file as the raw request body (not multipart), e.g. `fetch(url, {body: file})`.

    Streaming the raw body lets us count bytes as they arrive and abort at the limit, instead
    of letting a multipart parser buffer an arbitrarily large upload to disk first.
    """
    settings = get_settings()
    assert_can_access(session, user, collection_id, Action.WRITE)
    enforce_rate_limit(redis, "upload", str(user.id), limit=30, window_seconds=3600)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes:
        raise _too_large(settings.max_upload_bytes)

    doc_count = session.scalar(
        select(func.count()).select_from(Document).where(Document.collection_id == collection_id)
    )
    if doc_count >= settings.max_documents_per_collection:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A collection can hold at most {settings.max_documents_per_collection} files",
        )
    used = session.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.uploaded_by == user.id
        )
    )

    display_name = safe_display_name(filename)
    temp_path = storage.new_temp_path()
    try:
        size, digest = 0, hashlib.sha256()
        with temp_path.open("wb") as out:
            try:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise _too_large(settings.max_upload_bytes)
                    digest.update(chunk)
                    out.write(chunk)
            except ClientDisconnect:
                # Browser tab closed or a proxy dropped the connection: an expected event,
                # not a server error. The partial file is removed in `finally` below.
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="The upload was interrupted"
                ) from None
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty")
        if used + size > settings.user_storage_quota_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="You've reached your storage limit. Delete some files first.",
            )

        try:
            kind = detect_kind(temp_path, display_name)
        except UploadRejected as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from None

        sha256 = digest.hexdigest()
        duplicate = session.scalar(
            select(Document.id).where(
                Document.collection_id == collection_id, Document.sha256 == sha256
            )
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This file is already in this collection",
            )

        document = Document(
            collection_id=collection_id,
            uploaded_by=user.id,
            filename=display_name,
            kind=kind,
            size_bytes=size,
            sha256=sha256,
            storage_key=storage.new_key(),
        )
        storage.commit_temp(temp_path, document.storage_key)
        session.add(document)
        try:
            session.commit()
        except IntegrityError:
            # Same file uploaded concurrently: the unique constraint caught the race.
            session.rollback()
            storage.delete(document.storage_key)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This file is already in this collection",
            ) from None
        except Exception:
            session.rollback()
            storage.delete(document.storage_key)
            raise
    finally:
        temp_path.unlink(missing_ok=True)  # no-op once moved into place

    try:
        enqueue(document.id)
    except Exception:
        logger.exception("failed to enqueue document_id=%s", document.id)
        mark_failed(session, document.id, "Couldn't start processing. Please try again.")
        session.refresh(document)
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    collection_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[Document]:
    assert_can_access(session, user, collection_id, Action.READ)
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.collection_id == collection_id)
            .order_by(Document.created_at.desc())
        )
    )
    expire_stale(session, documents)
    return documents


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    collection_id: uuid.UUID, document_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Document:
    assert_can_access(session, user, collection_id, Action.READ)
    document = _get_document(session, collection_id, document_id)
    expire_stale(session, [document])
    return document


@router.get("/{document_id}/file")
def download_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> FileResponse:
    assert_can_access(session, user, collection_id, Action.READ)
    document = _get_document(session, collection_id, document_id)
    return FileResponse(
        storage.path_for(document.storage_key),
        media_type=_MEDIA_TYPES[document.kind],  # from detected type, never client-supplied
        filename=document.filename,
        content_disposition_type="attachment",
        # If a browser ever renders this inline, block scripts and same-origin access.
        headers={"Content-Security-Policy": "sandbox", "Cache-Control": "private, no-store"},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> None:
    assert_can_access(session, user, collection_id, Action.WRITE)
    document = _get_document(session, collection_id, document_id)
    key = document.storage_key
    session.delete(document)  # pages cascade in the database
    session.commit()
    storage.delete(key)
