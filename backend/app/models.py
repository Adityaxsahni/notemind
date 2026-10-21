import enum
import uuid
from collections.abc import Sequence
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(enum.StrEnum):
    OWNER = "owner"
    VIEWER = "viewer"


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _str_enum(cls: type[enum.StrEnum], name: str) -> Enum:
    """Postgres enum storing the lowercase values ("owner"), not member names ("OWNER")."""
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Granted only from the command line (python -m app.admin), never through the API.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = _created_at()


class RefreshToken(Base):
    """Opaque refresh tokens, stored only as SHA-256 hashes.

    Tokens issued from the same login share a family_id. Presenting an already-used
    token means it was stolen or replayed, so the whole family is revoked.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class Collection(Base):
    """A course, e.g. "DBMS Sem 5". Private to its owner unless shared via invite."""

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created_at()


class CollectionMember(Base):
    """Users a collection has been shared with. The owner is not stored here."""

    __tablename__ = "collection_members"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[Role] = mapped_column(_str_enum(Role, "collection_role"))
    created_at: Mapped[datetime] = _created_at()


class DocumentKind(enum.StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"  # a photo or scan of notes (JPEG, PNG, WebP); its text is transcribed


class DocumentStatus(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"
    # The same file uploaded twice to one collection is a no-op, not a second copy.
    __table_args__ = (UniqueConstraint("collection_id", "sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # display only, never used in paths
    kind: Mapped[DocumentKind] = mapped_column(_str_enum(DocumentKind, "document_kind"))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[DocumentStatus] = mapped_column(
        _str_enum(DocumentStatus, "document_status"), default=DocumentStatus.QUEUED
    )
    progress: Mapped[int] = mapped_column(default=0)
    page_count: Mapped[int | None]
    # Pages read from images (handwriting, scans) rather than a text layer.
    transcribed_pages: Mapped[int] = mapped_column(default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300))  # user-safe message only
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentPage(Base):
    """Cleaned text of one PDF page / slide / DOCX section. Source for chunking and citations."""

    __tablename__ = "document_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    page_number: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)


EMBEDDING_DIM = 384  # bge-small-en-v1.5; a different model needs a migration and a re-index


class Chunk(Base):
    """A retrievable passage of one page, with its embedding and full-text index.

    user_id is the collection owner's id, copied here so every search can filter on
    (user_id, collection_id) inside the SQL query itself (CLAUDE.md rule 1).
    """

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "position"),
        Index("ix_chunks_user_id_collection_id", "user_id", "collection_id"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    position: Mapped[int]  # reading order within the document
    page: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    embedding: Mapped[Sequence[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # Headings weigh more than body text in keyword ranking (ts_rank uses A > B).
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(heading, '')), 'A') || "
            "setweight(to_tsvector('english', text), 'B')",
            persisted=True,
        ),
    )


class InviteLink(Base):
    __tablename__ = "invite_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class AuditLog(Base):
    """Append-only record of admin and security-relevant actions (who did what, when).

    The app's database role can insert and (for admins) read these rows, never change or
    delete them. actor_id has no foreign key so the trail outlives deleted accounts; the
    client address is stored only as a keyed hash.
    """

    __tablename__ = "audit_log"
    # The app may insert but not read these rows back (row-level security), so no RETURNING.
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # None: command line
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    ip_hash: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AnalyticsEvent(Base):
    """A page view from a visitor who accepted analytics. No user id, IP, or cookie: just
    which page, from which site, on what kind of device."""

    __tablename__ = "analytics_events"
    # The app may insert but not read these rows back (row-level security), so no RETURNING.
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    path: Mapped[str] = mapped_column(String(200))
    referrer_host: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[str] = mapped_column(String(16))  # "mobile" | "desktop"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
