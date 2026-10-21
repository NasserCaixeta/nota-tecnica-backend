"""Separate participation, administrative authority and audit history."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0005"
down_revision = "20260707_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "users",
        sa.Column("participation_status", sa.String(9), nullable=False, server_default="pending"),
    )
    op.add_column(
        "users",
        sa.Column("participation_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("users", sa.Column("participation_reason", sa.String(1000), nullable=True))
    op.execute(
        sa.text(
            "UPDATE users SET is_admin = true, participation_status = 'approved' "
            "WHERE lower(profile_type) = 'admin'"
        )
    )
    # Legacy SQLAlchemy enums persist member names. Accept old lower-case exports too.
    op.execute(sa.text("UPDATE users SET profile_type = upper(profile_type)"))
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(120), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_target_id", "audit_events", ["target_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    for name in (
        "participation_reason",
        "participation_version",
        "participation_status",
        "is_admin",
    ):
        op.drop_column("users", name)
