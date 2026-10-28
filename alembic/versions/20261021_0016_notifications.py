"""Transactional notification inbox and durable email delivery outbox."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0016"
down_revision = "20261021_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notification_id", sa.Integer(), sa.ForeignKey("notifications.id"), nullable=False
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(80), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("notification_id", "channel", name="uq_notification_channel"),
    )
    op.create_index(
        "ix_notification_deliveries_notification_id", "notification_deliveries", ["notification_id"]
    )
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM notifications")):
        raise RuntimeError("Cannot discard participant notifications")
    op.drop_table("notification_deliveries")
    op.drop_table("notifications")
