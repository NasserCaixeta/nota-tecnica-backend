"""Moderated workshop representation and private supporting documents."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0007"
down_revision = "20261021_0006b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workshop_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workshop_id", sa.Integer(), sa.ForeignKey("workshops.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="PENDING"),
        sa.Column("review_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workshop_id", "user_id", name="uq_workshop_claim"),
    )
    op.create_index("ix_workshop_claims_user_id", "workshop_claims", ["user_id"])
    with op.batch_alter_table("documents") as batch:
        batch.alter_column("vehicle_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("workshop_claim_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_documents_workshop_claim", "workshop_claims", ["workshop_claim_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_document_subject",
            "(vehicle_id IS NOT NULL AND workshop_claim_id IS NULL) OR "
            "(vehicle_id IS NULL AND workshop_claim_id IS NOT NULL AND vehicle_link_id IS NULL "
            "AND maintenance_record_id IS NULL)",
        )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM documents WHERE workshop_claim_id IS NOT NULL")
    ):
        raise RuntimeError("Cannot remove workshop claims while their private evidence exists")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("ck_document_subject", type_="check")
        batch.drop_constraint("fk_documents_workshop_claim", type_="foreignkey")
        batch.drop_column("workshop_claim_id")
        batch.alter_column("vehicle_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("workshop_claims")
