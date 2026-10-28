from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models import ValidationDocumentType
from app.modules.documents.schemas import DocumentRead
from app.modules.vehicles.models import GarageValidationStatus, VehicleRelationshipType
from app.modules.vehicles.schemas import VehicleCreate


class GaragePermissions(BaseModel):
    can_add_maintenance: bool
    can_upload_documents: bool
    can_submit_review: bool
    can_share_history: bool
    can_generate_sale_report: bool


class GarageVehicleCreate(VehicleCreate):
    relationship_type: VehicleRelationshipType = VehicleRelationshipType.OWNER
    relationship_note: str | None = Field(default=None, max_length=500)


class GarageRelationshipUpdate(BaseModel):
    relationship_type: VehicleRelationshipType
    relationship_note: str | None = Field(default=None, max_length=500)


class GarageDocumentChecklist(BaseModel):
    required: list[ValidationDocumentType]
    uploaded: list[ValidationDocumentType]
    missing: list[ValidationDocumentType]
    missing_uploads: list[ValidationDocumentType] = Field(default_factory=list)
    awaiting_review: list[ValidationDocumentType] = Field(default_factory=list)
    rejected: list[ValidationDocumentType] = Field(default_factory=list)
    approved: list[ValidationDocumentType] = Field(default_factory=list)


class GarageRecommendedWorkshop(BaseModel):
    workshop_id: int
    trade_name: str
    city: str
    state: str
    score: float


class GarageVehicleItem(BaseModel):
    vehicle_id: int
    vehicle_link_id: int
    plate: str
    brand: str
    model: str
    model_year: int
    relationship_type: VehicleRelationshipType
    garage_status: GarageValidationStatus
    commercial_access: Literal["free", "subscription", "read_only"]
    admin_review_note: str | None = None
    verification_rejection_reason: str | None
    review_attempts: int
    review_version: int = 1
    permissions: GaragePermissions
    documents: GarageDocumentChecklist
    maintenance_alerts: list[dict[str, str]]
    recommended_workshops: list[GarageRecommendedWorkshop]
    created_at: datetime
    updated_at: datetime


class GarageSummary(BaseModel):
    total: int
    pending_documents: int
    under_review: int
    active: int
    rejected: int
    payment_required: int
    has_free_vehicle_slot: bool


class GarageDashboard(BaseModel):
    summary: GarageSummary
    vehicles: list[GarageVehicleItem]


class GarageReviewSubmitResponse(BaseModel):
    vehicle_link_id: int
    garage_status: GarageValidationStatus
    missing_documents: list[ValidationDocumentType]


class AdminGarageVehicleLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_link_id: int
    vehicle_id: int
    user_id: int
    plate: str
    relationship_type: VehicleRelationshipType
    garage_status: GarageValidationStatus
    required_documents: list[ValidationDocumentType]
    uploaded_documents: list[ValidationDocumentType]
    missing_documents: list[ValidationDocumentType]
    verification_rejection_reason: str | None
    review_attempts: int
    submitted_for_review_at: datetime | None
    reviewed_at: datetime | None
    review_version: int
    approved_documents: list[ValidationDocumentType]
    awaiting_review_documents: list[ValidationDocumentType]
    rejected_documents: list[ValidationDocumentType]
    documents: list[DocumentRead]
    admin_review_note: str | None
    user_full_name: str


class AdminAdditionalDocumentsRequest(BaseModel):
    expected_version: int = Field(ge=1)
    requested_document_types: list[ValidationDocumentType] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=500)


class MoneyAmount(BaseModel):
    amount: Decimal


class GarageFreeVehicleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_id: int = Field(gt=0)
