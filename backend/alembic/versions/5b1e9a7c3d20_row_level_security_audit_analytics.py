"""row-level security, admin flag, audit log, analytics events

Revision ID: 5b1e9a7c3d20
Revises: c7fdf68b85dc
Create Date: 2026-10-21 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app import rls

revision: str = "5b1e9a7c3d20"
down_revision: str | None = "c7fdf68b85dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY_TABLES = (
    "collections",
    "collection_members",
    "invite_links",
    "documents",
    "document_pages",
    "chunks",
)


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False)
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("ip_hash", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False),
        sa.Column("referrer_host", sa.String(length=100), nullable=True),
        sa.Column("device", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"])
    rls.apply(op.execute)


def downgrade() -> None:
    for table in (*_POLICY_TABLES, "audit_log", "analytics_events"):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for name in (
        "app_is_admin()",
        "app_document_owner(uuid)",
        "app_find_invite(text)",
        "app_has_open_invite(uuid)",
        "app_writable_collections()",
        "app_readable_collections()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {name} CASCADE")
    op.drop_table("analytics_events")
    op.drop_table("audit_log")
    op.drop_column("users", "is_admin")
