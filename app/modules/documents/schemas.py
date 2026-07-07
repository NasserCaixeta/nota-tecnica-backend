from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.documents.models import (
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    DocumentUploadStatus,
)


class DocumentCreate(BaseModel):
    maintenance_record_id: int | None = None
    document_type: DocumentType
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    storage_key: str = Field(min_length=1, max_length=512)


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class DocumentUploadIntentCreate(BaseModel):
    maintenance_record_id: int | None = None
    document_type: DocumentType
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    file_size_bytes: int | None = Field(default=None, ge=0)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DOCUMENT_CONTENT_TYPES:
            raise ValueError("Unsupported document content type")
        return normalized


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
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus
    original_file_name: str
    file_size_bytes: int | None
    uploaded_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class DocumentReviewUpdate(BaseModel):
    review_status: DocumentReviewStatus
    rejection_reason: str | None = Field(default=None, max_length=1000)


class DocumentUploadIntentRead(BaseModel):
    document: DocumentRead
    upload_url: str
    storage_key: str
    required_headers: dict[str, str]


class DocumentUploadConfirm(BaseModel):
    file_size_bytes: int | None = Field(default=None, ge=0)
