"""maintenance documents validation

Revision ID: 20260630_0002
Revises: 20260629_0001
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260630_0002"
down_revision: str | None = "20260629_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vehicle_users",
        sa.Column("verification_rejection_reason", sa.String(length=500), nullable=True),
    )
    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("odometer", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=10), nullable=False),
        sa.Column("vehicle_system", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("labor_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("parts_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("warranty_months", sa.Integer(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column("promised_delivery_date", sa.Date(), nullable=True),
        sa.Column("actual_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
    )
    op.create_index("ix_maintenance_records_id", "maintenance_records", ["id"])
    op.create_index("ix_maintenance_records_vehicle_id", "maintenance_records", ["vehicle_id"])
    op.create_index(
        "ix_maintenance_records_author_user_id",
        "maintenance_records",
        ["author_user_id"],
    )
    op.create_index("ix_maintenance_records_workshop_id", "maintenance_records", ["workshop_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("maintenance_record_id", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(length=15), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("review_status", sa.String(length=8), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["maintenance_record_id"], ["maintenance_records.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_documents_owner_user_id", "documents", ["owner_user_id"])
    op.create_index("ix_documents_vehicle_id", "documents", ["vehicle_id"])
    op.create_index("ix_documents_maintenance_record_id", "documents", ["maintenance_record_id"])
    op.create_index("ix_documents_storage_key", "documents", ["storage_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_documents_storage_key", table_name="documents")
    op.drop_index("ix_documents_maintenance_record_id", table_name="documents")
    op.drop_index("ix_documents_vehicle_id", table_name="documents")
    op.drop_index("ix_documents_owner_user_id", table_name="documents")
    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_maintenance_records_workshop_id", table_name="maintenance_records")
    op.drop_index("ix_maintenance_records_author_user_id", table_name="maintenance_records")
    op.drop_index("ix_maintenance_records_vehicle_id", table_name="maintenance_records")
    op.drop_index("ix_maintenance_records_id", table_name="maintenance_records")
    op.drop_table("maintenance_records")
    op.drop_column("vehicle_users", "verification_rejection_reason")
