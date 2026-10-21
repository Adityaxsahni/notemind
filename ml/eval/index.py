"""Searchable indexes of a set's courses, one per chunking configuration.

Each (course, chunk config) becomes a collection in a separate `notemind_eval` database,
built with the app's own extraction, cleaning, chunking and embedding code. Indexes are
reused across runs until the course files or the config change.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.config import get_settings
from app.embeddings import Embedder
from app.ingestion.chunking import chunk_pages, with_heading
from app.ingestion.clean import clean_pages
from app.ingestion.extract import extract_pages
from app.models import Base, Chunk, Collection, Document, DocumentKind, DocumentStatus, User

from .corpus import corpus_fingerprint, course_files

logger = logging.getLogger(__name__)

EVAL_DATABASE = "notemind_eval"
MODEL_MAX_TOKENS = 512  # bge-small reads at most this many tokens; the rest is ignored


@dataclass(frozen=True)
class ChunkConfig:
    target: int
    overlap: int

    @property
    def label(self) -> str:
        return f"{self.target}/{self.overlap}"


@dataclass(frozen=True)
class CourseIndex:
    owner_id: uuid.UUID
    collection_id: uuid.UUID
    chunks: int
    mean_tokens: float
    truncated: int  # chunks longer than the embedding model reads


def eval_engine() -> Engine:
    """The eval database on the dev Postgres server, created on first use."""
    url = make_url(get_settings().database_url).set(database=EVAL_DATABASE)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": EVAL_DATABASE}
        ):
            conn.execute(text(f'CREATE DATABASE "{EVAL_DATABASE}"'))
    admin.dispose()
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # The eval database is a disposable cache. create_all never alters existing tables,
        # so rebuild it whenever the app's models change.
        fingerprint = _schema_fingerprint(engine)
        conn.execute(text("CREATE TABLE IF NOT EXISTS eval_schema (fingerprint text)"))
        if conn.scalar(text("SELECT fingerprint FROM eval_schema")) != fingerprint:
            Base.metadata.drop_all(conn)
            conn.execute(text("DELETE FROM eval_schema"))
            conn.execute(text("INSERT INTO eval_schema VALUES (:f)"), {"f": fingerprint})
    Base.metadata.create_all(engine)
    return engine


def _schema_fingerprint(engine: Engine) -> str:
    ddl = ";".join(str(CreateTable(table).compile(engine)) for table in Base.metadata.sorted_tables)
    return hashlib.sha256(ddl.encode()).hexdigest()[:16]


COMBINED = "*"  # index key when every course shares one collection


def build_indexes(
    session: Session,
    embedder: Embedder,
    set_name: str,
    config: ChunkConfig,
    *,
    combined: bool = False,
) -> dict[str, CourseIndex]:
    """course -> index. With `combined`, all courses go into one collection under COMBINED,
    like a student keeping every course in one place: more distractors per question."""
    owner = _eval_user(session, set_name)
    courses = course_files(set_name)
    if combined:
        files = [f for course_files_ in courses.values() for f in course_files_]
        return {
            COMBINED: _course_index(
                session, embedder, owner, set_name, sorted(courses), files, config
            )
        }
    return {
        course: _course_index(session, embedder, owner, set_name, [course], files, config)
        for course, files in courses.items()
    }


def _eval_user(session: Session, set_name: str) -> User:
    email = f"eval-{set_name}@eval.invalid"
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash="!")  # noqa: S106  # not a hash: can never log in
        session.add(user)
        session.commit()
    return user


def _course_index(session, embedder, owner, set_name, courses, files, config) -> CourseIndex:
    fingerprint = hashlib.sha256(
        "".join(corpus_fingerprint(set_name, c) for c in courses).encode()
    ).hexdigest()[:12]
    name = f"{set_name}/{'+'.join(courses)} {config.label} {fingerprint}"
    collection = session.scalar(
        select(Collection).where(Collection.owner_id == owner.id, Collection.name == name)
    )
    if collection is None:
        started = time.perf_counter()
        collection = Collection(owner_id=owner.id, name=name)
        session.add(collection)
        session.flush()
        for path in files:
            _index_file(session, embedder, owner, collection, path, config)
        session.commit()
        logger.info("indexed %s in %.1fs", name, time.perf_counter() - started)

    count, mean_tokens, truncated = session.execute(
        select(
            func.count(),
            func.avg(Chunk.token_count),
            func.count().filter(Chunk.token_count > MODEL_MAX_TOKENS - 2),  # [CLS]/[SEP]
        ).where(Chunk.collection_id == collection.id)
    ).one()
    return CourseIndex(owner.id, collection.id, count, float(mean_tokens or 0), truncated)


def _index_file(session, embedder, owner, collection, path, config) -> None:
    data = path.read_bytes()
    kind = DocumentKind(path.suffix.lower().lstrip("."))
    document = Document(
        collection_id=collection.id,
        uploaded_by=owner.id,
        filename=path.name,
        kind=kind,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=uuid.uuid4().hex,  # files stay in the eval folder; nothing is stored
        status=DocumentStatus.READY,
        progress=100,
    )
    session.add(document)
    session.flush()

    pages = [p for p in clean_pages(extract_pages(path, kind)) if p.text]
    document.page_count = max((p.number for p in pages), default=0)
    # chunk_pages directly, not via settings: experiments may exceed the app's limits.
    drafts = chunk_pages(pages, kind, embedder.count_tokens, config.target, config.overlap)
    vectors = embedder.embed_documents([with_heading(d.heading, d.text) for d in drafts])
    session.add_all(
        Chunk(
            user_id=owner.id,
            collection_id=collection.id,
            document_id=document.id,
            position=i,
            page=d.page,
            heading=d.heading,
            text=d.text,
            token_count=d.token_count,
            embedding=v,
        )
        for i, (d, v) in enumerate(zip(drafts, vectors, strict=True))
    )
