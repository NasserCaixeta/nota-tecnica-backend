"""Separate vehicle relationships from commercial garage membership."""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0006"
down_revision = "20261021_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("free_garage_vehicle_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key(
            "fk_users_free_garage_vehicle", "vehicles", ["free_garage_vehicle_id"], ["id"]
        )
    op.create_table(
        "garage_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "vehicle_id", name="uq_garage_membership"),
    )
    op.create_index("ix_garage_memberships_user_id", "garage_memberships", ["user_id"])
    op.execute(
        sa.text("""INSERT INTO garage_memberships (user_id, vehicle_id, created_at)
        SELECT user_id, vehicle_id, created_at FROM vehicle_users ORDER BY id""")
    )
    op.execute(
        sa.text("""UPDATE users SET free_garage_vehicle_id = (
        SELECT vehicle_id FROM vehicle_users WHERE vehicle_users.user_id = users.id
        ORDER BY id LIMIT 1)""")
    )
    op.execute(
        sa.text("""UPDATE vehicle_users SET garage_status = CASE
        WHEN upper(garage_status) = 'PAYMENT_REQUIRED' THEN 'PENDING_DOCUMENTS'
        ELSE upper(garage_status) END,
        verification_status = upper(verification_status),
        relationship_type = upper(relationship_type)
        """)
    )


def downgrade() -> None:
    op.drop_table("garage_memberships")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_free_garage_vehicle", type_="foreignkey")
        batch.drop_column("free_garage_vehicle_id")
