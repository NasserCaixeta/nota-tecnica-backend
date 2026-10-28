"""Durable checkout lifecycle events and financial decision audit versions."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0015"
down_revision = "20261021_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "verified_payments",
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subscription_cancellations",
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "checkout_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("provider_checkout_id", sa.String(200), nullable=False),
        sa.Column("order_reference", sa.String(200), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(80), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "environment", "event_id", name="uq_checkout_event"),
    )
    op.create_index(
        "ix_checkout_events_provider_checkout_id", "checkout_events", ["provider_checkout_id"]
    )
    op.create_index("ix_checkout_events_status", "checkout_events", ["status"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM checkout_events")):
        raise RuntimeError("Cannot discard checkout lifecycle events")
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM verified_payments WHERE decision_version > 0")
    ):
        raise RuntimeError("Cannot discard audited payment versions")
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM subscription_cancellations WHERE decision_version > 1")
    ):
        raise RuntimeError("Cannot discard audited cancellation versions")
    op.drop_table("checkout_events")
    op.drop_column("subscription_cancellations", "decision_version")
    op.drop_column("verified_payments", "decision_version")
