from datetime import UTC, datetime, timedelta

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.integrations.storage.r2 import StorageClient, build_document_storage_key
from app.modules.audit.service import append_audit
from app.modules.documents.access import require_document_owner, require_document_reader
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentUploadStatus,
)
from app.modules.documents.schemas import (
    DocumentCreate,
    DocumentDownloadRead,
    DocumentUploadConfirm,
    DocumentUploadIntentCreate,
    DocumentUploadIntentRead,
)
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.users.models import User
from app.modules.vehicles.access import require_vehicle_link
from app.modules.vehicles.models import GarageValidationStatus, Vehicle, VehicleUser


async def ensure_maintenance_record_belongs_to_vehicle(
    session: AsyncSession,
    vehicle_id: int,
    maintenance_record_id: int | None,
    user: User,
) -> None:
    if maintenance_record_id is None:
        return
    record = await session.get(MaintenanceRecord, maintenance_record_id)
    if record is None or record.author_user_id != user.id:
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
    raise HTTPException(status_code=410, detail="Use the document upload-intents flow")


async def create_document_upload_intent(
    session: AsyncSession,
    vehicle_id: int,
    payload: DocumentUploadIntentCreate,
    user: User,
    storage_client: StorageClient,
) -> DocumentUploadIntentRead:
    await require_vehicle_link(session, user.id, vehicle_id)
    vehicle = await session.get(Vehicle, vehicle_id)
    await ensure_maintenance_record_belongs_to_vehicle(
        session,
        vehicle_id,
        payload.maintenance_record_id,
        user,
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
        .with_for_update(of=VehicleUser)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle link not found")
    vehicle, link = row
    if link.garage_status not in {
        GarageValidationStatus.PENDING_DOCUMENTS,
        GarageValidationStatus.REJECTED,
    }:
        raise HTTPException(
            status_code=409, detail="Documents cannot be changed in the current review status"
        )
    if payload.validation_document_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validation document type is required",
        )
    await ensure_maintenance_record_belongs_to_vehicle(
        session,
        vehicle.id,
        payload.maintenance_record_id,
        user,
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
    await require_vehicle_link(session, user.id, vehicle_id)
    result = await session.execute(
        select(Document)
        .where(Document.vehicle_id == vehicle_id, Document.owner_user_id == user.id)
        .order_by(Document.id)
    )
    return list(result.scalars().all())


async def get_document(session: AsyncSession, document_id: int, user: User) -> Document:
    document = await session.get(Document, document_id)
    return require_document_reader(document, user)


async def confirm_document_upload(
    session: AsyncSession,
    document_id: int,
    payload: DocumentUploadConfirm,
    user: User,
    storage_client: StorageClient,
) -> Document:
    document = require_document_owner(
        await session.scalar(
            select(Document)
            .where(
                Document.id == document_id,
            )
            .with_for_update()
        ),
        user,
    )
    if document.upload_status == DocumentUploadStatus.UPLOADED and document.storage_verified:
        return document
    try:
        info = await run_in_threadpool(storage_client.inspect_object, document.storage_key)
        if not info.exists:
            raise HTTPException(status_code=409, detail="The document has not been uploaded")
        if not 0 < info.size_bytes <= 10 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="Document size exceeds the allowed limit")
        if info.content_type != document.content_type:
            raise HTTPException(status_code=422, detail="The uploaded document type is invalid")
        for declared in (document.file_size_bytes, payload.file_size_bytes):
            if declared is not None and declared != info.size_bytes:
                raise HTTPException(
                    status_code=422, detail="Document size differs from the uploaded file"
                )
        final_key = await run_in_threadpool(
            storage_client.finalize_upload, document.storage_key, info.etag
        )
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from exc
    document.storage_key = final_key
    document.upload_status = DocumentUploadStatus.UPLOADED
    document.storage_verified = True
    document.review_status = DocumentReviewStatus.PENDING
    document.processing_status = DocumentProcessingStatus.NOT_REQUESTED
    document.file_size_bytes = info.size_bytes
    document.uploaded_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(document)
    return document


async def get_document_download(
    session: AsyncSession,
    document_id: int,
    actor: User,
    storage: StorageClient,
) -> DocumentDownloadRead:
    document = await get_document(session, document_id, actor)
    if document.upload_status != DocumentUploadStatus.UPLOADED or not document.storage_verified:
        raise HTTPException(status_code=409, detail="The document has not been uploaded")
    try:
        url = storage.create_presigned_download_url(document.storage_key, expires_seconds=300)
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(
            status_code=503, detail="Document storage is temporarily unavailable"
        ) from exc
    if actor.is_admin and actor.id != document.owner_user_id:
        await append_audit(
            session,
            actor_id=actor.id,
            action="document.download",
            target_type="document",
            target_id=document.id,
        )
        await session.commit()
    return DocumentDownloadRead(url=url, expires_at=datetime.now(UTC) + timedelta(seconds=300))
