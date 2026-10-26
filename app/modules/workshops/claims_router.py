from collections.abc import Callable
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.storage.r2 import StorageClient, safe_file_name
from app.modules.auth.dependencies import get_approved_participant
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    DocumentUploadStatus,
)
from app.modules.documents.router import get_storage_client
from app.modules.documents.schemas import DocumentUploadIntentCreate, DocumentUploadIntentRead
from app.modules.users.models import User
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.claims import CLAIM_DOCUMENT_TYPES
from app.modules.workshops.models import WorkshopClaim

router = APIRouter(prefix="/workshop-claims", tags=["workshop-claims"])


@router.post(
    "/{claim_id}/documents/upload-intents", response_model=DocumentUploadIntentRead, status_code=201
)
async def create_claim_upload(
    claim_id: int,
    payload: DocumentUploadIntentCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage_factory: Annotated[Callable[[], StorageClient], Depends(get_storage_client)],
):
    claim = await session.scalar(
        select(WorkshopClaim)
        .where(
            WorkshopClaim.id == claim_id,
            WorkshopClaim.user_id == actor.id,
        )
        .with_for_update()
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Representation request not found")
    if claim.status == VerificationStatus.VERIFIED:
        raise HTTPException(status_code=409, detail="Representation is already verified")
    if (
        payload.validation_document_type not in CLAIM_DOCUMENT_TYPES
        or payload.maintenance_record_id
    ):
        raise HTTPException(status_code=422, detail="A representation document type is required")
    storage: StorageClient = storage_factory()
    key = f"workshop-claims/{claim.id}/{uuid4()}-{safe_file_name(payload.file_name)}"
    document = Document(
        owner_user_id=actor.id,
        workshop_claim_id=claim.id,
        vehicle_id=None,
        document_type=DocumentType.OTHER,
        validation_document_type=payload.validation_document_type,
        file_name=payload.file_name,
        original_file_name=payload.file_name,
        content_type=payload.content_type,
        storage_key=key,
        file_size_bytes=payload.file_size_bytes,
    )
    document.upload_status = DocumentUploadStatus.PENDING
    document.review_status = DocumentReviewStatus.PENDING
    document.processing_status = DocumentProcessingStatus.NOT_REQUESTED
    session.add(document)
    await session.commit()
    signed = storage.create_presigned_upload_url(
        storage_key=key,
        content_type=payload.content_type,
        expires_seconds=get_settings().document_upload_url_expires_seconds,
    )
    return DocumentUploadIntentRead(
        document=document,
        storage_key=key,
        upload_url=signed.upload_url,
        required_headers=signed.required_headers,
    )
