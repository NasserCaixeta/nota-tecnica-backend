"""Single-use password recovery, session versions and administrative account requests."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0017"
down_revision = "20261021_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "password_recoveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("auth_version_at_issue", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_recoveries_user_id", "password_recoveries", ["user_id"])
    op.create_table(
        "account_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('closure', 'identity_correction')", name="ck_account_request_kind"
        ),
    )
    op.create_index("ix_account_requests_user_id", "account_requests", ["user_id"])
    op.create_index(
        "uq_pending_account_request",
        "account_requests",
        ["user_id", "kind"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM password_recoveries")
    ) or op.get_bind().scalar(sa.text("SELECT count(*) FROM account_requests")):
        raise RuntimeError("Cannot discard recovery or administrative request history")
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM users WHERE auth_version > 1")):
        raise RuntimeError("Cannot restore sessions invalidated by security action")
    op.drop_table("account_requests")
    op.drop_table("password_recoveries")
    op.drop_column("users", "auth_version")
