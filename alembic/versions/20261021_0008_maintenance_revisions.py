"""Version service data and withhold legacy completed entries from publication."""

import json
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "20261021_0008"
down_revision = "20261021_0007"
branch_labels = None
depends_on = None

VEHICLE_TEXT_FIELDS = (
    "brand",
    "model",
    "color",
    "vehicle_type",
    "chassis",
    "renavam",
    "fuel_type",
    "engine",
    "transmission",
)


def upgrade():
    op.create_table(
        "maintenance_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "record_id", sa.Integer(), sa.ForeignKey("maintenance_records.id"), nullable=False
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("editorial_status", sa.String(24), nullable=False),
        sa.Column("admin_status", sa.String(24), nullable=False),
        sa.Column("customer_acknowledgement", sa.String(32), nullable=False),
        sa.Column("customer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("record_id", "revision_number", name="uq_maintenance_revision"),
    )
    op.create_index("ix_maintenance_revisions_record_id", "maintenance_revisions", ["record_id"])
    op.add_column(
        "maintenance_records",
        sa.Column("origin", sa.String(16), nullable=False, server_default="customer"),
    )
    op.add_column(
        "maintenance_records", sa.Column("current_revision_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_current_revision",
        "maintenance_records",
        "maintenance_revisions",
        ["current_revision_id"],
        ["id"],
    )
    op.add_column(
        "maintenance_records",
        sa.Column("dispute_open", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("maintenance_records", sa.Column("superseded_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_maintenance_superseded",
        "maintenance_records",
        "maintenance_records",
        ["superseded_by_id"],
        ["id"],
    )
    op.add_column("documents", sa.Column("maintenance_revision_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_document_maintenance_revision",
        "documents",
        "maintenance_revisions",
        ["maintenance_revision_id"],
        ["id"],
    )
    op.create_index(
        "ix_documents_maintenance_revision_id", "documents", ["maintenance_revision_id"]
    )
    op.add_column("vehicle_users", sa.Column("declared_vehicle_data", sa.JSON(), nullable=True))
    for field in VEHICLE_TEXT_FIELDS:
        op.alter_column("vehicles", field, nullable=True)
    op.alter_column("vehicles", "model_year", nullable=True)
    conn = op.get_bind()
    fields = (
        "workshop_id",
        "service_date",
        "odometer",
        "category",
        "vehicle_system",
        "description",
        "labor_cost",
        "parts_cost",
        "warranty_months",
        "entry_date",
        "promised_delivery_date",
        "actual_delivery_date",
        "status",
    )
    table = sa.table(
        "maintenance_revisions",
        sa.column("id", sa.Integer()),
        sa.column("record_id", sa.Integer()),
        sa.column("revision_number", sa.Integer()),
        sa.column("snapshot", sa.JSON()),
        sa.column("editorial_status"),
        sa.column("admin_status"),
        sa.column("customer_acknowledgement"),
        sa.column("customer_user_id", sa.Integer()),
        sa.column("review_version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for row in conn.execute(sa.text("SELECT * FROM maintenance_records ORDER BY id")).mappings():
        snapshot = {key: row[key] for key in fields}
        for field in ("category", "vehicle_system", "status"):
            snapshot[field] = snapshot[field].lower()
        snapshot = json.loads(json.dumps(snapshot, default=str))
        new_id = conn.execute(
            table.insert()
            .values(
                record_id=row["id"],
                revision_number=1,
                snapshot=snapshot,
                editorial_status="draft",
                admin_status="pending",
                customer_acknowledgement="author_acknowledged",
                customer_user_id=row["author_user_id"],
                review_version=1,
                created_at=datetime.now(UTC),
            )
            .returning(table.c.id)
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE maintenance_records SET current_revision_id=:rid WHERE id=:id"),
            {"rid": new_id, "id": row["id"]},
        )
        conn.execute(
            sa.text(
                "UPDATE documents SET maintenance_revision_id=:rid WHERE maintenance_record_id=:id"
            ),
            {"rid": new_id, "id": row["id"]},
        )


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM maintenance_revisions")):
        raise RuntimeError("Cannot discard service revision history; restore a backup instead")
    if conn.scalar(
        sa.text("SELECT count(*) FROM vehicles WHERE chassis IS NULL OR renavam IS NULL")
    ):
        raise RuntimeError("Cannot remove plate references without losing data")
    op.drop_constraint("fk_document_maintenance_revision", "documents", type_="foreignkey")
    op.drop_index("ix_documents_maintenance_revision_id", table_name="documents")
    op.drop_column("documents", "maintenance_revision_id")
    op.drop_constraint("fk_current_revision", "maintenance_records", type_="foreignkey")
    op.drop_constraint("fk_maintenance_superseded", "maintenance_records", type_="foreignkey")
    for field in ("current_revision_id", "origin", "dispute_open", "superseded_by_id"):
        op.drop_column("maintenance_records", field)
    op.drop_table("maintenance_revisions")
    op.drop_column("vehicle_users", "declared_vehicle_data")
    for field in (*VEHICLE_TEXT_FIELDS, "model_year"):
        op.alter_column("vehicles", field, nullable=False)
