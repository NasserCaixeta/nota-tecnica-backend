from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, Text
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
