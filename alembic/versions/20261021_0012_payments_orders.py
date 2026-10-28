"""Persist immutable checkout intent before contacting the Sandbox provider."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0012"
down_revision = "20261021_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product", sa.String(32), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("provider_checkout_id", sa.String(200), unique=True, nullable=True),
        sa.Column("provider_subscription_id", sa.String(200), unique=True, nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("callback_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_payment_positive_amount"),
        sa.CheckConstraint("currency = 'BRL'", name="ck_payment_currency"),
        sa.CheckConstraint("environment = 'sandbox'", name="ck_payment_sandbox"),
        sa.CheckConstraint(
            "product IN ('history_access', 'garage_monthly')", name="ck_payment_product"
        ),
        sa.CheckConstraint(
            "(product = 'history_access' AND vehicle_id IS NOT NULL) OR "
            "(product = 'garage_monthly' AND vehicle_id IS NULL)",
            name="ck_payment_target",
        ),
    )
    op.create_index("ix_payment_orders_buyer_id", "payment_orders", ["buyer_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM payment_orders")):
        raise RuntimeError("Cannot discard payment orders")
    op.drop_table("payment_orders")
