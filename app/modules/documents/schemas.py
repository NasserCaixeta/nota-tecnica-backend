from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models import DocumentReviewStatus, DocumentType


class DocumentCreate(BaseModel):
    maintenance_record_id: int | None = None
    document_type: DocumentType
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    storage_key: str = Field(min_length=1, max_length=512)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    vehicle_id: int
    maintenance_record_id: int | None
    document_type: DocumentType
    file_name: str
    content_type: str
    storage_key: str
    review_status: DocumentReviewStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class DocumentReviewUpdate(BaseModel):
    review_status: DocumentReviewStatus
    rejection_reason: str | None = Field(default=None, max_length=1000)
