"""garage validation flow

Revision ID: 20260707_0004
Revises: 20260706_0003
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260707_0004"
down_revision: str | None = "20260706_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vehicle_users",
        sa.Column(
            "garage_status",
            sa.String(length=17),
            nullable=False,
            server_default="pending_documents",
        ),
    )
    op.add_column("vehicle_users", sa.Column("relationship_note", sa.String(length=500)))
    op.add_column(
        "vehicle_users",
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True)),
    )
    op.add_column("vehicle_users", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column(
        "vehicle_users",
        sa.Column("review_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "vehicle_users",
        sa.Column("requested_document_types", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("vehicle_users", sa.Column("admin_review_note", sa.String(length=500)))
    op.add_column("documents", sa.Column("vehicle_link_id", sa.Integer()))
    op.add_column("documents", sa.Column("validation_document_type", sa.String(length=39)))
    op.create_index("ix_documents_vehicle_link_id", "documents", ["vehicle_link_id"])
    with op.batch_alter_table("documents") as batch_op:
        batch_op.create_foreign_key(
            "fk_documents_vehicle_link_id_vehicle_users",
            "vehicle_users",
            ["vehicle_link_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_vehicle_link_id_vehicle_users", type_="foreignkey")
    op.drop_index("ix_documents_vehicle_link_id", table_name="documents")
    op.drop_column("documents", "validation_document_type")
    op.drop_column("documents", "vehicle_link_id")
    op.drop_column("vehicle_users", "admin_review_note")
    op.drop_column("vehicle_users", "requested_document_types")
    op.drop_column("vehicle_users", "review_attempts")
    op.drop_column("vehicle_users", "reviewed_at")
    op.drop_column("vehicle_users", "submitted_for_review_at")
    op.drop_column("vehicle_users", "relationship_note")
    op.drop_column("vehicle_users", "garage_status")
