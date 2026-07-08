from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentReviewStatus
from app.modules.garage.schemas import AdminAdditionalDocumentsRequest
from app.modules.garage.service import build_admin_garage_vehicle_link_read
from app.modules.vehicles.models import (
    GarageValidationStatus,
    Vehicle,
    VehicleUser,
    VerificationStatus,
)


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


async def list_pending_garage_vehicle_links(session: AsyncSession):
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.garage_status == GarageValidationStatus.UNDER_REVIEW)
        .order_by(VehicleUser.submitted_for_review_at, VehicleUser.id)
    )
    return [
        await build_admin_garage_vehicle_link_read(session, vehicle, link)
        for vehicle, link in result.all()
    ]


async def review_garage_vehicle_link(
    session: AsyncSession,
    vehicle_link_id: int,
    verification_status: VerificationStatus,
    verification_rejection_reason: str | None,
):
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.id == vehicle_link_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    vehicle, link = row
    if verification_status == VerificationStatus.VERIFIED:
        link.verification_status = VerificationStatus.VERIFIED
        link.garage_status = GarageValidationStatus.ACTIVE
        link.verification_rejection_reason = None
    elif verification_status == VerificationStatus.REJECTED:
        if not verification_rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejection reason is required",
            )
        link.verification_status = VerificationStatus.REJECTED
        link.garage_status = GarageValidationStatus.REJECTED
        link.verification_rejection_reason = verification_rejection_reason
        link.review_attempts += 1
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review status must be verified or rejected",
        )
    link.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(link)
    return await build_admin_garage_vehicle_link_read(session, vehicle, link)


async def request_garage_additional_documents(
    session: AsyncSession,
    vehicle_link_id: int,
    payload: AdminAdditionalDocumentsRequest,
):
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.id == vehicle_link_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    vehicle, link = row
    existing = set(link.requested_document_types or [])
    for document_type in payload.requested_document_types:
        existing.add(document_type.value)
    link.requested_document_types = sorted(existing)
    link.admin_review_note = payload.note
    link.garage_status = GarageValidationStatus.PENDING_DOCUMENTS
    await session.commit()
    await session.refresh(link)
    return await build_admin_garage_vehicle_link_read(session, vehicle, link)
