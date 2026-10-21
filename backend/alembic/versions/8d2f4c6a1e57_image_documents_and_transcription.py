"""image documents and transcribed page count

Revision ID: 8d2f4c6a1e57
Revises: 5b1e9a7c3d20
Create Date: 2026-10-21 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d2f4c6a1e57"
down_revision: str | None = "5b1e9a7c3d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_kind ADD VALUE IF NOT EXISTS 'image'")
    op.add_column(
        "documents",
        sa.Column("transcribed_pages", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("documents", "transcribed_pages")
    # Postgres can't drop an enum value: rebuild the type without it.
    op.execute("DELETE FROM documents WHERE kind = 'image'")
    op.execute("ALTER TYPE document_kind RENAME TO document_kind_old")
    op.execute("CREATE TYPE document_kind AS ENUM ('pdf', 'docx', 'pptx')")
    op.execute(
        "ALTER TABLE documents ALTER COLUMN kind TYPE document_kind USING kind::text::document_kind"
    )
    op.execute("DROP TYPE document_kind_old")
