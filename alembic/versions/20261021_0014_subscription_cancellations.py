"""Durable subscription cancellation requests for safe remote recovery."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0014"
down_revision = "20261021_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscription_cancellations",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payment_orders.id"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_subscription_cancellations_status", "subscription_cancellations", ["status"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM subscription_cancellations")):
        raise RuntimeError("Cannot discard subscription cancellations")
    op.drop_table("subscription_cancellations")
