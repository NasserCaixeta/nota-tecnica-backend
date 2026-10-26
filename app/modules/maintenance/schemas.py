from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.validators import validate_brazilian_plate
from app.modules.garage.schemas import GarageVehicleCreate
from app.modules.maintenance.models import MaintenanceCategory, MaintenanceStatus, VehicleSystem


class MaintenanceRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
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

    @model_validator(mode="after")
    def coherent_dates(self):
        for end in (self.promised_delivery_date, self.actual_delivery_date):
            if self.entry_date and end and end < self.entry_date:
                raise ValueError("Delivery cannot precede entry")
        return self


class WorkshopMaintenanceCreate(MaintenanceRecordCreate):
    plate: str

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value):
        return validate_brazilian_plate(value)


class MaintenanceRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision_id: int | None = Field(default=None, ge=1)
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
    origin: str
    current_revision_id: int
    editorial_status: str
    admin_status: str
    customer_acknowledgement: str
    customer_user_id: int | None
    review_version: int
    public_description: str | None
    review_reason: str | None
    published: bool
    superseded_by_id: int | None
    dispute_open: bool


class MaintenanceSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: int = Field(ge=1)


class MaintenanceReview(MaintenanceSubmit):
    expected_version: int = Field(ge=1)
    decision: Literal["approved", "rejected", "changes_requested"]
    reason: str = Field(min_length=1, max_length=2000)
    public_description: str | None = Field(default=None, min_length=1, max_length=2000)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InvitationCreate(MaintenanceSubmit):
    recipient_email: EmailStr


class InvitationAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=64, max_length=256)


class InvitationRelationship(InvitationAccept):
    vehicle: GarageVehicleCreate


class ServiceAssociation(MaintenanceSubmit):
    other_record_id: int = Field(ge=1)
    other_revision_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
