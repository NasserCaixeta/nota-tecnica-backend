from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.documents.models import Document


class MaintenanceCategory(StrEnum):
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    BODYWORK = "bodywork"
    PAINT = "paint"
    DETAILING = "detailing"
    TIRES = "tires"
    INSPECTION = "inspection"
    DIAGNOSIS = "diagnosis"
    OTHER = "other"


class VehicleSystem(StrEnum):
    ENGINE = "engine"
    TRANSMISSION = "transmission"
    BRAKES = "brakes"
    SUSPENSION = "suspension"
    AIR_CONDITIONING = "air_conditioning"
    STEERING = "steering"
    ELECTRICAL = "electrical"
    INTERIOR = "interior"
    BODY = "body"
    PAINT = "paint"
    DETAILING = "detailing"
    TIRES = "tires"
    OTHER = "other"


class MaintenanceStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(16), default="customer", nullable=False)
    current_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_revisions.id", use_alter=True, name="fk_current_revision"),
        nullable=True,
    )
    dispute_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_records.id"), nullable=True
    )
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workshop_id: Mapped[int | None] = mapped_column(
        ForeignKey("workshops.id"),
        nullable=True,
        index=True,
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    odometer: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[MaintenanceCategory] = mapped_column(
        Enum(MaintenanceCategory, native_enum=False),
        nullable=False,
    )
    vehicle_system: Mapped[VehicleSystem] = mapped_column(
        Enum(VehicleSystem, native_enum=False),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    parts_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    warranty_months: Mapped[int | None] = mapped_column(nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    promised_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="maintenance_record",
    )


class MaintenanceRevision(Base):
    __tablename__ = "maintenance_revisions"
    __table_args__ = (
        UniqueConstraint("record_id", "revision_number", name="uq_maintenance_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"), index=True)
    revision_number: Mapped[int] = mapped_column(nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    editorial_status: Mapped[str] = mapped_column(String(24), default="draft")
    admin_status: Mapped[str] = mapped_column(String(24), default="pending")
    customer_acknowledgement: Mapped[str] = mapped_column(String(32))
    customer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_version: Mapped[int] = mapped_column(default=1)
    public_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ServiceInvitation(Base):
    __tablename__ = "service_invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("maintenance_revisions.id"))
    recipient_email: Mapped[str] = mapped_column(String(255))
    nonce: Mapped[str] = mapped_column(String(64), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class InvitationIntent(Base):
    __tablename__ = "invitation_intents"
    __table_args__ = (UniqueConstraint("invitation_id", "user_id", name="uq_invitation_intent"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("service_invitations.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ServiceDuplicateProposal(Base):
    __tablename__ = "service_duplicate_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"))
    other_record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"))
    revision_id: Mapped[int] = mapped_column(ForeignKey("maintenance_revisions.id"))
    other_revision_id: Mapped[int] = mapped_column(ForeignKey("maintenance_revisions.id"))
    proposed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
