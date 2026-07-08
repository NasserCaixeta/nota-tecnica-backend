from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.maintenance.models import MaintenanceRecord


class DocumentType(StrEnum):
    CRLV = "crlv"
    INVOICE = "invoice"
    SERVICE_ORDER = "service_order"
    PHOTO_BEFORE = "photo_before"
    PHOTO_AFTER = "photo_after"
    PAYMENT_RECEIPT = "payment_receipt"
    WARRANTY = "warranty"
    OTHER = "other"


class DocumentReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentUploadStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


class DocumentProcessingStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ValidationDocumentType(StrEnum):
    CRLV = "crlv"
    OWNER_AUTHORIZATION = "owner_authorization"
    RELATIONSHIP_PROOF = "relationship_proof"
    COMPANY_CONTRACT_OR_POWER_OF_ATTORNEY = "company_contract_or_power_of_attorney"
    REPRESENTATIVE_IDENTITY = "representative_identity"
    FLEET_AUTHORIZATION = "fleet_authorization"
    PURCHASE_RECEIPT_OR_ATPV = "purchase_receipt_or_atpv"
    DRIVER_IDENTITY = "driver_identity"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    maintenance_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("maintenance_records.id"),
        nullable=True,
        index=True,
    )
    vehicle_link_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle_users.id"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False),
        nullable=False,
    )
    validation_document_type: Mapped[ValidationDocumentType | None] = mapped_column(
        Enum(ValidationDocumentType, native_enum=False),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        Enum(DocumentReviewStatus, native_enum=False),
        nullable=False,
    )
    upload_status: Mapped[DocumentUploadStatus] = mapped_column(
        Enum(DocumentUploadStatus, native_enum=False),
        nullable=False,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(DocumentProcessingStatus, native_enum=False),
        nullable=False,
    )
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    maintenance_record: Mapped["MaintenanceRecord | None"] = relationship(
        "MaintenanceRecord",
        back_populates="documents",
    )
