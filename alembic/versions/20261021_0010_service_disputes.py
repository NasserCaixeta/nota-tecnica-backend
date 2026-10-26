"""Preserve customer disputes, replies and private evidence."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0010"
down_revision = "20261021_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_disputes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column(
            "revision_id", sa.Integer(), sa.ForeignKey("maintenance_revisions.id"), nullable=False
        ),
        sa.Column("customer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resolution", sa.String(24), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_service_disputes_record_id", "service_disputes", ["record_id"])
    op.create_table(
        "service_dispute_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispute_id", sa.Integer(), sa.ForeignKey("service_disputes.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("documents", sa.Column("service_dispute_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_document_service_dispute",
        "documents",
        "service_disputes",
        ["service_dispute_id"],
        ["id"],
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM service_disputes")):
        raise RuntimeError("Cannot discard recorded customer disputes")
    op.drop_constraint("fk_document_service_dispute", "documents", type_="foreignkey")
    op.drop_column("documents", "service_dispute_id")
    op.drop_table("service_dispute_messages")
    op.drop_table("service_disputes")
