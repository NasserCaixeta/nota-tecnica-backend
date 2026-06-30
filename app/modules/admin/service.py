from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentReviewStatus
from app.modules.vehicles.models import VehicleUser, VerificationStatus


async def review_vehicle_link(
    session: AsyncSession,
    vehicle_link_id: int,
    verification_status: VerificationStatus,
    verification_rejection_reason: str | None,
) -> VehicleUser:
    link = await session.get(VehicleUser, vehicle_link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    link.verification_status = verification_status
    if verification_status == VerificationStatus.REJECTED:
        link.verification_rejection_reason = verification_rejection_reason
    else:
        link.verification_rejection_reason = None
    await session.commit()
    await session.refresh(link)
    return link


async def review_document(
    session: AsyncSession,
    document_id: int,
    review_status: DocumentReviewStatus,
    rejection_reason: str | None,
) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document.review_status = review_status
    document.rejection_reason = (
        rejection_reason if review_status == DocumentReviewStatus.REJECTED else None
    )
    await session.commit()
    await session.refresh(document)
    return document
