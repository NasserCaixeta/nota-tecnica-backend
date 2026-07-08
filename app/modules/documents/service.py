from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.storage.r2 import StorageClient, build_document_storage_key
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentUploadStatus,
)
from app.modules.documents.schemas import (
    DocumentCreate,
    DocumentUploadConfirm,
    DocumentUploadIntentCreate,
    DocumentUploadIntentRead,
)
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.service import ensure_user_vehicle_link
from app.modules.users.models import User
from app.modules.vehicles.models import GarageValidationStatus, Vehicle, VehicleUser


async def ensure_maintenance_record_belongs_to_vehicle(
    session: AsyncSession,
    vehicle_id: int,
    maintenance_record_id: int | None,
) -> None:
    if maintenance_record_id is None:
        return
    record = await session.get(MaintenanceRecord, maintenance_record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance record not found",
        )
    if record.vehicle_id != vehicle_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maintenance record does not belong to vehicle",
        )


async def create_document(
    session: AsyncSession,
    vehicle_id: int,
    payload: DocumentCreate,
    user: User,
) -> Document:
    await ensure_user_vehicle_link(session, vehicle_id, user)
    duplicate = await session.execute(
        select(Document).where(Document.storage_key == payload.storage_key)
    )
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document storage key already registered",
        )
    await ensure_maintenance_record_belongs_to_vehicle(
        session,
        vehicle_id,
        payload.maintenance_record_id,
    )
    document = Document(
        **payload.model_dump(),
        vehicle_id=vehicle_id,
        owner_user_id=user.id,
        review_status=DocumentReviewStatus.PENDING,
        upload_status=DocumentUploadStatus.UPLOADED,
        processing_status=DocumentProcessingStatus.NOT_REQUESTED,
        original_file_name=payload.file_name,
        uploaded_at=datetime.now(UTC),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def create_document_upload_intent(
    session: AsyncSession,
    vehicle_id: int,
    payload: DocumentUploadIntentCreate,
    user: User,
    storage_client: StorageClient,
) -> DocumentUploadIntentRead:
    vehicle = await ensure_user_vehicle_link(session, vehicle_id, user)
    await ensure_maintenance_record_belongs_to_vehicle(
        session,
        vehicle_id,
        payload.maintenance_record_id,
    )
    storage_key = build_document_storage_key(vehicle.plate, payload.file_name)
    document = Document(
        owner_user_id=user.id,
        vehicle_id=vehicle_id,
        maintenance_record_id=payload.maintenance_record_id,
        document_type=payload.document_type,
        file_name=payload.file_name,
        original_file_name=payload.file_name,
        content_type=payload.content_type,
        storage_key=storage_key,
        file_size_bytes=payload.file_size_bytes,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.NOT_REQUESTED,
        review_status=DocumentReviewStatus.PENDING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    presigned_upload = storage_client.create_presigned_upload_url(
        storage_key=storage_key,
        content_type=payload.content_type,
        expires_seconds=get_settings().document_upload_url_expires_seconds,
    )
    return DocumentUploadIntentRead(
        document=document,
        upload_url=presigned_upload.upload_url,
        storage_key=storage_key,
        required_headers=presigned_upload.required_headers,
    )


async def create_vehicle_link_document_upload_intent(
    session: AsyncSession,
    vehicle_link_id: int,
    payload: DocumentUploadIntentCreate,
    user: User,
    storage_client: StorageClient,
) -> DocumentUploadIntentRead:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.id == vehicle_link_id, VehicleUser.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle link not found")
    vehicle, link = row
    if link.garage_status == GarageValidationStatus.PAYMENT_REQUIRED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment required")
    if payload.validation_document_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validation document type is required",
        )
    await ensure_maintenance_record_belongs_to_vehicle(
        session,
        vehicle.id,
        payload.maintenance_record_id,
    )
    storage_key = build_document_storage_key(vehicle.plate, payload.file_name)
    document = Document(
        owner_user_id=user.id,
        vehicle_id=vehicle.id,
        vehicle_link_id=link.id,
        maintenance_record_id=payload.maintenance_record_id,
        document_type=payload.document_type,
        validation_document_type=payload.validation_document_type,
        file_name=payload.file_name,
        original_file_name=payload.file_name,
        content_type=payload.content_type,
        storage_key=storage_key,
        file_size_bytes=payload.file_size_bytes,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.NOT_REQUESTED,
        review_status=DocumentReviewStatus.PENDING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    presigned_upload = storage_client.create_presigned_upload_url(
        storage_key=storage_key,
        content_type=payload.content_type,
        expires_seconds=get_settings().document_upload_url_expires_seconds,
    )
    return DocumentUploadIntentRead(
        document=document,
        upload_url=presigned_upload.upload_url,
        storage_key=storage_key,
        required_headers=presigned_upload.required_headers,
    )


async def list_vehicle_documents(
    session: AsyncSession,
    vehicle_id: int,
    user: User,
) -> list[Document]:
    await ensure_user_vehicle_link(session, vehicle_id, user)
    result = await session.execute(
        select(Document).where(Document.vehicle_id == vehicle_id).order_by(Document.id)
    )
    return list(result.scalars().all())


async def get_document(session: AsyncSession, document_id: int, user: User) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await ensure_user_vehicle_link(session, document.vehicle_id, user)
    return document


async def confirm_document_upload(
    session: AsyncSession,
    document_id: int,
    payload: DocumentUploadConfirm,
    user: User,
) -> Document:
    document = await get_document(session, document_id, user)
    document.upload_status = DocumentUploadStatus.UPLOADED
    document.processing_status = DocumentProcessingStatus.PENDING
    if payload.file_size_bytes is not None:
        document.file_size_bytes = payload.file_size_bytes
    document.uploaded_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(document)
    return document
