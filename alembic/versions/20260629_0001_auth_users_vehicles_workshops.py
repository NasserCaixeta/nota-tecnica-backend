"""auth users vehicles workshops

Revision ID: 20260629_0001
Revises:
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260629_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("cpf", sa.String(length=11), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("profile_type", sa.String(length=14), nullable=False),
        sa.Column("zip_code", sa.String(length=16), nullable=False),
        sa.Column("street", sa.String(length=255), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("neighborhood", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("complement", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_cpf", "users", ["cpf"], unique=True)

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plate", sa.String(length=16), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("model_year", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=60), nullable=False),
        sa.Column("vehicle_type", sa.String(length=60), nullable=False),
        sa.Column("chassis", sa.String(length=32), nullable=False),
        sa.Column("renavam", sa.String(length=32), nullable=False),
        sa.Column("fuel_type", sa.String(length=60), nullable=False),
        sa.Column("engine", sa.String(length=120), nullable=False),
        sa.Column("transmission", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vehicles_id", "vehicles", ["id"])
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"], unique=True)
    op.create_index("ix_vehicles_chassis", "vehicles", ["chassis"], unique=True)
    op.create_index("ix_vehicles_renavam", "vehicles", ["renavam"], unique=True)

    op.create_table(
        "vehicle_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=22), nullable=False),
        sa.Column("verification_status", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("vehicle_id", "user_id", name="uq_vehicle_users_link"),
    )
    op.create_index("ix_vehicle_users_id", "vehicle_users", ["id"])

    op.create_table(
        "workshops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("zip_code", sa.String(length=16), nullable=False),
        sa.Column("street", sa.String(length=255), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("neighborhood", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("complement", sa.String(length=120), nullable=True),
        sa.Column("specialties", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=14), nullable=False),
        sa.Column("verification_status", sa.String(length=8), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_workshops_id", "workshops", ["id"])
    op.create_index("ix_workshops_cnpj", "workshops", ["cnpj"], unique=True)

    op.create_table(
        "workshop_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=7), nullable=False),
        sa.Column("verification_status", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("workshop_id", "user_id", name="uq_workshop_users_link"),
    )
    op.create_index("ix_workshop_users_id", "workshop_users", ["id"])


def downgrade() -> None:
    op.drop_index("ix_workshop_users_id", table_name="workshop_users")
    op.drop_table("workshop_users")
    op.drop_index("ix_workshops_cnpj", table_name="workshops")
    op.drop_index("ix_workshops_id", table_name="workshops")
    op.drop_table("workshops")
    op.drop_index("ix_vehicle_users_id", table_name="vehicle_users")
    op.drop_table("vehicle_users")
    op.drop_index("ix_vehicles_renavam", table_name="vehicles")
    op.drop_index("ix_vehicles_chassis", table_name="vehicles")
    op.drop_index("ix_vehicles_plate", table_name="vehicles")
    op.drop_index("ix_vehicles_id", table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index("ix_users_cpf", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
