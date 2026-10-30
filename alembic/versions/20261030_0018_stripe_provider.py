"""Identify legacy orders without sending their IDs to the new Stripe provider."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_0018"
down_revision = "20261021_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment_orders",
        sa.Column("provider", sa.String(20), nullable=False, server_default="asaas"),
    )
    op.alter_column("payment_orders", "provider", server_default=None)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM payment_orders WHERE provider='stripe'")):
        raise RuntimeError("Cannot discard Stripe order ownership history")
    op.drop_column("payment_orders", "provider")
