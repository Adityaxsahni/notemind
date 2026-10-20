"""Background ingestion: extract → clean → store pages. Chunking/embedding arrive in Phase 5."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.db import new_session
from app.ingestion.clean import clean_pages
from app.ingestion.extract import ExtractionError, extract_pages
from app.models import Document, DocumentPage, DocumentStatus
from app.storage import LocalStorage, get_storage

logger = logging.getLogger(__name__)

JOB_TIMEOUT_SECONDS = 180
STALE_AFTER = timedelta(minutes=15)
WORKER_MEMORY_LIMIT_BYTES = 2 * 1024**3

GENERIC_FAILURE = "We couldn't read this file. It may be damaged; try re-saving it as PDF."
NO_TEXT_FAILURE = (
    "No text found. Scanned or handwritten documents need OCR, which isn't supported yet."
)
TIMEOUT_FAILURE = "Processing took too long or used too much memory. Try a smaller file."


def ingest_document(session: Session, storage: LocalStorage, document_id: uuid.UUID) -> None:
    document = session.get(Document, document_id)
    if document is None or document.status == DocumentStatus.READY:
        return  # deleted while queued, or already processed (job retried)

    document.status = DocumentStatus.PROCESSING
    document.progress = 10
    session.commit()

    try:
        pages = extract_pages(storage.path_for(document.storage_key), document.kind)
        document.progress = 60
        session.commit()

        pages = [p for p in clean_pages(pages) if p.text]
        if not pages:
            raise ExtractionError(NO_TEXT_FAILURE)

        # Idempotent: a retried job replaces whatever a previous attempt stored.
        session.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        session.add_all(
            DocumentPage(document_id=document.id, page_number=p.number, text=p.text) for p in pages
        )
        document.page_count = max(p.number for p in pages)
        document.status = DocumentStatus.READY
        document.progress = 100
        document.error = None
        session.commit()
    except ExtractionError as exc:
        session.rollback()
        mark_failed(session, document_id, str(exc))
    except Exception:
        session.rollback()
        # Log the ID and traceback only; never document content (CLAUDE.md rule 3).
        logger.exception("ingestion failed for document_id=%s", document_id)
        mark_failed(session, document_id, GENERIC_FAILURE)


def mark_failed(session: Session, document_id: uuid.UUID, message: str) -> None:
    session.execute(
        update(Document)
        .where(Document.id == document_id, Document.status != DocumentStatus.READY)
        .values(status=DocumentStatus.FAILED, error=message[:300], progress=0)
    )
    session.commit()


def expire_stale(session: Session, documents: list[Document]) -> None:
    """A worker killed mid-job (OOM, deploy) leaves documents stuck; surface them as failed."""
    cutoff = datetime.now(UTC) - STALE_AFTER
    stale = [
        d
        for d in documents
        if d.status in (DocumentStatus.QUEUED, DocumentStatus.PROCESSING) and d.updated_at < cutoff
    ]
    for document in stale:
        document.status = DocumentStatus.FAILED
        document.error = TIMEOUT_FAILURE
    if stale:
        session.commit()


# --- RQ entrypoints (run in the worker's forked work-horse process) -------------------------


def _limit_memory() -> None:
    try:
        import resource
    except ImportError:  # Windows: no rlimits; Docker's mem_limit still applies
        return
    resource.setrlimit(resource.RLIMIT_AS, (WORKER_MEMORY_LIMIT_BYTES, WORKER_MEMORY_LIMIT_BYTES))


def process_document(document_id: str) -> None:
    # RQ forks a fresh process per job, so this limit dies with the job.
    _limit_memory()
    session = new_session()
    try:
        ingest_document(session, get_storage(), uuid.UUID(document_id))
    finally:
        session.close()


def on_job_failure(job, connection, exc_type, exc_value, tb) -> None:
    """Called by RQ when the job crashes or exceeds its timeout."""
    session = new_session()
    try:
        mark_failed(session, uuid.UUID(job.args[0]), TIMEOUT_FAILURE)
    finally:
        session.close()
