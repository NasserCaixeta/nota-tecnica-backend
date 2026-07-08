from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VehicleRelationshipType(StrEnum):
    OWNER = "owner"
    SPOUSE = "spouse"
    FAMILY = "family"
    COMPANY_REPRESENTATIVE = "company_representative"
    FLEET_RESPONSIBLE = "fleet_responsible"
    RECENT_BUYER = "recent_buyer"
    AUTHORIZED_DRIVER = "authorized_driver"
    OTHER = "other"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class GarageValidationStatus(StrEnum):
    PENDING_DOCUMENTS = "pending_documents"
    UNDER_REVIEW = "under_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    PAYMENT_REQUIRED = "payment_required"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    plate: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    brand: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    model_year: Mapped[int] = mapped_column(nullable=False)
    color: Mapped[str] = mapped_column(String(60), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(60), nullable=False)
    chassis: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    renavam: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(60), nullable=False)
    engine: Mapped[str] = mapped_column(String(120), nullable=False)
    transmission: Mapped[str] = mapped_column(String(60), nullable=False)
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

    user_links: Mapped[list["VehicleUser"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )


class VehicleUser(Base):
    __tablename__ = "vehicle_users"
    __table_args__ = (UniqueConstraint("vehicle_id", "user_id", name="uq_vehicle_users_link"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    relationship_type: Mapped[VehicleRelationshipType] = mapped_column(
        Enum(VehicleRelationshipType, native_enum=False),
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False),
        nullable=False,
    )
    verification_rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    garage_status: Mapped[GarageValidationStatus] = mapped_column(
        Enum(GarageValidationStatus, native_enum=False),
        nullable=False,
        default=GarageValidationStatus.PENDING_DOCUMENTS,
    )
    relationship_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_for_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    requested_document_types: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    admin_review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
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

    vehicle: Mapped[Vehicle] = relationship(back_populates="user_links")
