"""Private one-time invitations and explicit duplicate proposals."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0009"
down_revision = "20261021_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column(
            "revision_id", sa.Integer(), sa.ForeignKey("maintenance_revisions.id"), nullable=False
        ),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_service_invitations_record_id", "service_invitations", ["record_id"])
    op.create_index(
        "ix_service_invitations_token_hash", "service_invitations", ["token_hash"], unique=True
    )
    op.create_table(
        "invitation_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "invitation_id", sa.Integer(), sa.ForeignKey("service_invitations.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invitation_id", "user_id", name="uq_invitation_intent"),
    )
    op.create_table(
        "service_duplicate_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column(
            "other_record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column(
            "revision_id", sa.Integer(), sa.ForeignKey("maintenance_revisions.id"), nullable=False
        ),
        sa.Column(
            "other_revision_id",
            sa.Integer(),
            sa.ForeignKey("maintenance_revisions.id"),
            nullable=False,
        ),
        sa.Column("proposed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM service_invitations")):
        raise RuntimeError("Cannot discard invitation and acknowledgement history")
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM service_duplicate_proposals")):
        raise RuntimeError("Cannot discard duplicate decisions")
    op.drop_table("service_duplicate_proposals")
    op.drop_table("invitation_intents")
    op.drop_table("service_invitations")
