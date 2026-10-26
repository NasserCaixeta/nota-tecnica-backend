"""Legacy uploaded markers do not imply inspected and immutable evidence."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0006a"
down_revision = "20261021_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("storage_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("documents", "storage_verified")
