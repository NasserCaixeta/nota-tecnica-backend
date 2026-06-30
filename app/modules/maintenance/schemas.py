from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.maintenance.models import MaintenanceCategory, MaintenanceStatus, VehicleSystem


class MaintenanceRecordCreate(BaseModel):
    workshop_id: int | None = None
    service_date: date
    odometer: int = Field(ge=0)
    category: MaintenanceCategory
    vehicle_system: VehicleSystem
    description: str = Field(min_length=1)
    labor_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    parts_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    warranty_months: int | None = Field(default=None, ge=0)
    entry_date: date | None = None
    promised_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: MaintenanceStatus = MaintenanceStatus.COMPLETED


class MaintenanceRecordUpdate(BaseModel):
    workshop_id: int | None = None
    service_date: date | None = None
    odometer: int | None = Field(default=None, ge=0)
    category: MaintenanceCategory | None = None
    vehicle_system: VehicleSystem | None = None
    description: str | None = Field(default=None, min_length=1)
    labor_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    parts_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    warranty_months: int | None = Field(default=None, ge=0)
    entry_date: date | None = None
    promised_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    status: MaintenanceStatus | None = None


class MaintenanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    author_user_id: int
    workshop_id: int | None
    service_date: date
    odometer: int
    category: MaintenanceCategory
    vehicle_system: VehicleSystem
    description: str
    labor_cost: Decimal
    parts_cost: Decimal
    total_cost: Decimal
    warranty_months: int | None
    entry_date: date | None
    promised_delivery_date: date | None
    actual_delivery_date: date | None
    status: MaintenanceStatus
    created_at: datetime
    updated_at: datetime
