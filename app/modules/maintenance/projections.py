from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.modules.maintenance.schemas import MaintenanceRecordCreate
from app.modules.vehicles.models import VerificationStatus


class PublishedWorkshopRead(BaseModel):
    id: int
    trade_name: str
    verified: bool


class PublishedMaintenanceRead(BaseModel):
    visibility: Literal["published"] = "published"
    id: int
    service_date: date
    odometer: int
    category: str
    vehicle_system: str
    public_description: str
    workshop: PublishedWorkshopRead | None
    labor_cost: Decimal
    parts_cost: Decimal
    total_cost: Decimal


def build_published_maintenance_read(record, revision, workshop) -> PublishedMaintenanceRead:
    """Project an eligible current revision; the caller must use the canonical selection."""
    if (
        revision.id != record.current_revision_id
        or revision.record_id != record.id
        or revision.admin_status != "approved"
        or not revision.public_description
    ):
        raise ValueError("Only a reviewed current revision can be projected")
    data = MaintenanceRecordCreate(**revision.snapshot)
    return PublishedMaintenanceRead(
        id=record.id,
        service_date=data.service_date,
        odometer=data.odometer,
        category=data.category.value,
        vehicle_system=data.vehicle_system.value,
        public_description=revision.public_description,
        workshop=PublishedWorkshopRead(
            id=workshop.id,
            trade_name=workshop.trade_name,
            verified=workshop.verification_status == VerificationStatus.VERIFIED,
        )
        if workshop
        else None,
        labor_cost=data.labor_cost,
        parts_cost=data.parts_cost,
        total_cost=data.labor_cost + data.parts_cost,
    )
