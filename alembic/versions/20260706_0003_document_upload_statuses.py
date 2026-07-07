"""document upload statuses

Revision ID: 20260706_0003
Revises: 20260630_0002
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260706_0003"
down_revision: str | None = "20260630_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("upload_status", sa.String(length=8), nullable=False, server_default="uploaded"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "processing_status",
            sa.String(length=13),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("original_file_name", sa.String(length=255), nullable=True),
    )
    op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE documents SET original_file_name = file_name WHERE original_file_name IS NULL"
    )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("original_file_name", nullable=False)


def downgrade() -> None:
    op.drop_column("documents", "uploaded_at")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "original_file_name")
    op.drop_column("documents", "processing_status")
    op.drop_column("documents", "upload_status")
