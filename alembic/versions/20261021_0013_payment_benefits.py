"""Durable authenticated event inbox and benefits tied to verified payments."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0013"
down_revision = "20261021_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("provider_payment_id", sa.String(200), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(80), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "environment", "event_id", name="uq_payment_event"),
    )
    op.create_index(
        "ix_payment_events_provider_payment_id", "payment_events", ["provider_payment_id"]
    )
    op.create_index("ix_payment_events_status", "payment_events", ["status"])
    op.create_table(
        "verified_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payment_orders.id"), nullable=False),
        sa.Column("provider_payment_id", sa.String(200), unique=True, nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verified_payments_order_id", "verified_payments", ["order_id"])
    op.create_table(
        "history_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("payment_orders.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("verified_payments.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > starts_at", name="ck_history_access_range"),
    )
    op.create_index("ix_history_access_grants_buyer_id", "history_access_grants", ["buyer_id"])
    op.create_table(
        "subscription_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payment_orders.id"), nullable=False),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("verified_payments.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_subscription_id", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > starts_at", name="ck_subscription_period_range"),
    )
    op.create_index("ix_subscription_periods_order_id", "subscription_periods", ["order_id"])
    op.create_index("ix_subscription_periods_buyer_id", "subscription_periods", ["buyer_id"])
    op.create_index(
        "ix_subscription_periods_provider_subscription_id",
        "subscription_periods",
        ["provider_subscription_id"],
    )


def downgrade():
    for table in (
        "subscription_periods",
        "history_access_grants",
        "verified_payments",
        "payment_events",
    ):
        if op.get_bind().scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError("Cannot discard financial events or benefits")
    for table in (
        "subscription_periods",
        "history_access_grants",
        "verified_payments",
        "payment_events",
    ):
        op.drop_table(table)
