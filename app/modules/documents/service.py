from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentReviewStatus
from app.modules.documents.schemas import DocumentCreate
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.service import ensure_user_vehicle_link
from app.modules.users.models import User


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
    if payload.maintenance_record_id is not None:
        record = await session.get(MaintenanceRecord, payload.maintenance_record_id)
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
    document = Document(
        **payload.model_dump(),
        vehicle_id=vehicle_id,
        owner_user_id=user.id,
        review_status=DocumentReviewStatus.PENDING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


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
