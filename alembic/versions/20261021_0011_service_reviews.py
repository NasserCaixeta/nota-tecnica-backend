"""Reviews belong to the acknowledging customer and exact service revision."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0011"
down_revision = "20261021_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column(
            "revision_id", sa.Integer(), sa.ForeignKey("maintenance_revisions.id"), nullable=False
        ),
        sa.Column("customer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("comment_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("moderation_reason", sa.Text(), nullable=True),
        sa.Column("review_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("record_id", "customer_user_id", name="uq_service_review_customer"),
        sa.CheckConstraint("stars >= 1 AND stars <= 5", name="ck_review_stars"),
    )
    op.create_index("ix_service_reviews_record_id", "service_reviews", ["record_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM service_reviews")):
        raise RuntimeError("Cannot discard service reviews")
    op.drop_table("service_reviews")
