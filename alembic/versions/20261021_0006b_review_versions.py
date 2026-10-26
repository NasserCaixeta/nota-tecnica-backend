"""Version administrative decisions on documents and vehicle relationships."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0006b"
down_revision = "20261021_0006a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("documents", "vehicle_users"):
        op.add_column(
            table, sa.Column("review_version", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade() -> None:
    for table in ("documents", "vehicle_users"):
        op.drop_column(table, "review_version")
