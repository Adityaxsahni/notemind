"""Background jobs. Ingestion: extract → transcribe image-only pages → clean → store pages.
Indexing: chunk → embed → store.

They run on separate queues. Parsing untrusted files needs a fresh, memory-capped process per
job; embedding trusted text needs the model kept in memory between jobs.
"""

import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.config import get_settings
from app.db import new_session, set_rls_user
from app.embeddings import Embedder, get_embedder
from app.ingestion.chunking import chunk_pages, with_heading
from app.ingestion.clean import clean_pages
from app.ingestion.extract import ExtractionError, Page, extract_pages
from app.ingestion.ocr import (
    PageImage,
    Transcriber,
    get_ocr_provider,
    load_photo,
    make_transcriber,
    needs_transcription,
    render_pdf_pages,
)
from app.ingestion.queue import enqueue_indexing
from app.llm.gateway import BudgetExceeded, LLMNotConfigured
from app.llm.providers import LLMUnavailable
from app.models import Chunk, Collection, Document, DocumentKind, DocumentPage, DocumentStatus
from app.redis_client import get_redis
from app.storage import LocalStorage, get_storage

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)
WORKER_MEMORY_LIMIT_BYTES = 2 * 1024**3
EXTRACTED_PROGRESS = 50  # extraction is the first half of the progress bar, indexing the rest

GENERIC_FAILURE = "We couldn't read this file. It may be damaged; try re-saving it as PDF."
INDEXING_FAILURE = "Something went wrong while indexing this file. Please upload it again."
NO_TEXT_FAILURE = "No text found in this file."
TOO_MANY_SCANNED_PAGES = "Handwritten or scanned documents can have at most {} pages."
# Why handwriting couldn't be read. Mostly-typed documents are indexed without those pages.
TRANSCRIPTION_FAILURES = {
    LLMNotConfigured: "This file is handwritten or scanned. Reading handwriting needs an AI "
    "provider key, which this server doesn't have.",
    BudgetExceeded: "You've reached today's limit for reading handwritten pages. Delete this "
    "file and upload it again tomorrow.",
    LLMUnavailable: "The handwriting reader is busy right now. Delete this file and upload it "
    "again in a few minutes.",
}
TIMEOUT_FAILURE = "Processing took too long or used too much memory. Try a smaller file."


def act_as_document_owner(session: Session, document_id: uuid.UUID) -> None:
    """Jobs get only a document id from the API; row-level security needs a user, so they
    act as the owner of the document's collection (None if it was deleted meanwhile)."""
    owner_id = session.scalar(select(func.app_document_owner(document_id)))
    if owner_id is not None:
        set_rls_user(session, owner_id)


def ingest_document(
    session: Session,
    storage: LocalStorage,
    document_id: uuid.UUID,
    index: Callable[[uuid.UUID], None],
    transcriber_for: Callable[[uuid.UUID], Transcriber],
) -> None:
    act_as_document_owner(session, document_id)
    document = session.get(Document, document_id)
    if document is None or document.status == DocumentStatus.READY:
        return  # deleted while queued, or already processed (job retried)

    document.status = DocumentStatus.PROCESSING
    document.progress = 10
    session.commit()

    with _fail_on_error(session, document_id, GENERIC_FAILURE):
        path = storage.path_for(document.storage_key)
        pages = extract_pages(path, document.kind)
        document.progress = 15
        session.commit()

        pages, transcribed = _transcribe_image_pages(
            session, document, path, pages, transcriber_for
        )
        document.transcribed_pages = transcribed
        document.progress = 40
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
        document.progress = EXTRACTED_PROGRESS
        session.commit()
        index(document.id)


def _transcribe_image_pages(
    session: Session,
    document: Document,
    path: Path,
    pages: list[Page],
    transcriber_for: Callable[[uuid.UUID], Transcriber],
) -> tuple[list[Page], int]:
    """Replace pages that are pictures of text (handwriting, scans, photos) with their
    transcription. Returns the pages and how many were transcribed."""
    images: list[PageImage]
    if document.kind == DocumentKind.IMAGE:
        images = [load_photo(path)]
    elif document.kind == DocumentKind.PDF:
        numbers = [p.number for p in pages if needs_transcription(p.text)]
        limit = get_settings().ocr_max_pages
        if len(numbers) > limit:
            raise ExtractionError(TOO_MANY_SCANNED_PAGES.format(limit))
        images = list(render_pdf_pages(path, numbers))
    else:
        return pages, 0  # picture-only slides and Word pages are diagrams, not notes
    if not images:
        return pages, 0

    def progress(done: int) -> None:
        document.progress = 15 + 25 * done // len(images)
        session.commit()

    try:
        texts = transcriber_for(document.uploaded_by).transcribe(images, on_progress=progress)
    except tuple(TRANSCRIPTION_FAILURES) as exc:
        typed = sum(1 for p in pages if not needs_transcription(p.text))
        if typed >= len(images):
            logger.warning(
                "indexing document_id=%s without %d image pages: %s",
                document.id,
                len(images),
                type(exc).__name__,
            )
            return pages, 0
        raise ExtractionError(TRANSCRIPTION_FAILURES[type(exc)]) from None

    by_number = {p.number: p for p in pages}
    for number, text in texts.items():
        by_number[number] = Page(number=number, text=text)
    transcribed = sum(1 for text in texts.values() if text.strip())
    logger.info("transcribed document_id=%s pages=%d", document.id, transcribed)
    return sorted(by_number.values(), key=lambda p: p.number), transcribed


def index_document(session: Session, embedder: Embedder, document_id: uuid.UUID) -> None:
    """Chunk a document's stored pages, embed the chunks, and mark the document ready."""
    settings = get_settings()
    act_as_document_owner(session, document_id)
    document = session.get(Document, document_id)
    if document is None or document.status != DocumentStatus.PROCESSING:
        return  # deleted, already indexed, or failed while this job waited

    with _fail_on_error(session, document_id, INDEXING_FAILURE):
        owner_id = session.scalar(
            select(Collection.owner_id).where(Collection.id == document.collection_id)
        )
        stored = session.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
        drafts = chunk_pages(
            [Page(number=p.page_number, text=p.text) for p in stored],
            document.kind,
            embedder.count_tokens,
            settings.chunk_target_tokens,
            settings.chunk_overlap_tokens,
        )
        if not drafts:
            raise ExtractionError(NO_TEXT_FAILURE)

        vectors = []
        batch_size = settings.embedding_batch_size
        for start in range(0, len(drafts), batch_size):
            batch = drafts[start : start + batch_size]
            vectors.extend(
                embedder.embed_documents([with_heading(d.heading, d.text) for d in batch])
            )
            done = start + len(batch)
            # Each commit also bumps updated_at, so a long job is never mistaken for stale.
            document.progress = EXTRACTED_PROGRESS + (99 - EXTRACTED_PROGRESS) * done // len(drafts)
            session.commit()

        session.execute(delete(Chunk).where(Chunk.document_id == document.id))
        session.add_all(
            Chunk(
                user_id=owner_id,
                collection_id=document.collection_id,
                document_id=document.id,
                position=position,
                page=draft.page,
                heading=draft.heading,
                text=draft.text,
                token_count=draft.token_count,
                embedding=vector,
            )
            for position, (draft, vector) in enumerate(zip(drafts, vectors, strict=True))
        )
        document.status = DocumentStatus.READY
        document.progress = 100
        document.error = None
        session.commit()
        logger.info("indexed document_id=%s chunks=%d", document_id, len(drafts))


@contextmanager
def _fail_on_error(
    session: Session, document_id: uuid.UUID, generic_message: str
) -> Iterator[None]:
    try:
        yield
    except StaleDataError:
        session.rollback()  # the document was deleted while we worked on it; nothing to report
    except ExtractionError as exc:
        session.rollback()
        mark_failed(session, document_id, str(exc))
    except Exception:
        session.rollback()
        # Log the ID and traceback only; never document content (CLAUDE.md rule 3).
        logger.exception("processing failed for document_id=%s", document_id)
        mark_failed(session, document_id, generic_message)


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


# --- RQ entrypoints -------------------------------------------------------------------------


def _limit_memory() -> None:
    try:
        import resource
    except ImportError:  # Windows: no rlimits; Docker's mem_limit still applies
        return
    resource.setrlimit(resource.RLIMIT_AS, (WORKER_MEMORY_LIMIT_BYTES, WORKER_MEMORY_LIMIT_BYTES))


def process_document(document_id: str) -> None:
    # Runs in RQ's forked work-horse, so this limit dies with the job.
    _limit_memory()
    redis = get_redis()
    session = new_session()
    try:
        ingest_document(
            session,
            get_storage(),
            uuid.UUID(document_id),
            index=lambda doc_id: enqueue_indexing(redis, doc_id),
            transcriber_for=lambda user_id: make_transcriber(redis, user_id, get_ocr_provider()),
        )
    finally:
        session.close()


def index_document_job(document_id: str) -> None:
    session = new_session()
    try:
        index_document(session, get_embedder(), uuid.UUID(document_id))
    finally:
        session.close()


def on_job_failure(job, connection, exc_type, exc_value, tb) -> None:
    """Called by RQ when either job crashes or exceeds its timeout."""
    session = new_session()
    try:
        act_as_document_owner(session, uuid.UUID(job.args[0]))
        mark_failed(session, uuid.UUID(job.args[0]), TIMEOUT_FAILURE)
    finally:
        session.close()
