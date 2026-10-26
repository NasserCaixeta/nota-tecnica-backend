from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
from app.modules.documents.models import Document, DocumentReviewStatus, DocumentUploadStatus
from app.modules.garage.schemas import AdminAdditionalDocumentsRequest
from app.modules.garage.service import (
    build_admin_garage_vehicle_link_read,
    build_document_checklist,
    latest_validation_documents,
)
from app.modules.users.models import User
from app.modules.vehicles.models import (
    GarageValidationStatus,
    Vehicle,
    VehicleUser,
    VerificationStatus,
)


async def locked_vehicle_link(session, vehicle_link_id):
    row = (
        await session.execute(
            select(Vehicle, VehicleUser)
            .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
            .where(VehicleUser.id == vehicle_link_id)
            .with_for_update(of=VehicleUser)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return row


def check_review(actor, link, expected_version):
    if actor.id == link.user_id:
        raise HTTPException(
            status_code=409, detail="Administrators cannot review their own vehicle link"
        )
    if expected_version != link.review_version:
        raise HTTPException(status_code=409, detail="The review has changed; refresh the request")


async def get_admin_garage_vehicle_link(session, vehicle_link_id):
    row = (
        await session.execute(
            select(Vehicle, VehicleUser)
            .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
            .where(VehicleUser.id == vehicle_link_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return await build_admin_garage_vehicle_link_read(session, *row)


async def review_vehicle_link(
    session,
    vehicle_link_id,
    verification_status,
    verification_rejection_reason,
    *,
    actor,
    expected_version,
):
    await review_garage_vehicle_link(
        session,
        vehicle_link_id,
        verification_status,
        verification_rejection_reason,
        actor=actor,
        expected_version=expected_version,
    )
    return await session.get(VehicleUser, vehicle_link_id)


async def review_document(
    session: AsyncSession,
    document_id: int,
    review_status: DocumentReviewStatus,
    rejection_reason: str | None,
    *,
    actor: User,
    expected_version: int,
) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    claim = None
    link = None
    if document.workshop_claim_id is not None:
        from app.modules.workshops.claims import latest_claim_documents
        from app.modules.workshops.models import WorkshopClaim

        claim = await session.scalar(
            select(WorkshopClaim)
            .where(WorkshopClaim.id == document.workshop_claim_id)
            .with_for_update()
        )
        latest = await latest_claim_documents(session, claim.id)
        if document.id not in {item.id for item in latest}:
            raise HTTPException(status_code=409, detail="This evidence has been replaced")
    if document.vehicle_link_id is not None:
        _, link = await locked_vehicle_link(session, document.vehicle_link_id)
        latest = await latest_validation_documents(session, link)
        if document.id not in {item.id for item in latest}:
            raise HTTPException(status_code=409, detail="This evidence has been replaced")
    document = await session.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if document.owner_user_id == actor.id:
        raise HTTPException(
            status_code=409, detail="Administrators cannot review their own document"
        )
    if document.review_version != expected_version:
        raise HTTPException(
            status_code=409, detail="The document review has changed; refresh the request"
        )
    if not document.storage_verified or document.upload_status != DocumentUploadStatus.UPLOADED:
        raise HTTPException(
            status_code=409, detail="The document must be verified in storage first"
        )
    if review_status not in {DocumentReviewStatus.APPROVED, DocumentReviewStatus.REJECTED}:
        raise HTTPException(status_code=422, detail="Choose approved or rejected")
    if review_status == DocumentReviewStatus.REJECTED and not (rejection_reason or "").strip():
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    document.review_status = review_status
    document.rejection_reason = (
        rejection_reason if review_status == DocumentReviewStatus.REJECTED else None
    )
    document.review_version += 1
    if link is not None:
        link.review_version += 1
        if review_status == DocumentReviewStatus.REJECTED:
            link.garage_status = GarageValidationStatus.PENDING_DOCUMENTS
            link.verification_status = VerificationStatus.PENDING
            link.verification_rejection_reason = rejection_reason
    if claim is not None:
        claim.review_version += 1
        if review_status == DocumentReviewStatus.REJECTED:
            from app.modules.workshops.models import WorkshopUser

            claim.status = VerificationStatus.PENDING
            member = await session.scalar(
                select(WorkshopUser).where(
                    WorkshopUser.user_id == claim.user_id,
                    WorkshopUser.workshop_id == claim.workshop_id,
                )
            )
            if member is not None:
                member.verification_status = VerificationStatus.PENDING
    await append_audit(
        session,
        actor_id=actor.id,
        action="document.review",
        target_type="document",
        target_id=document.id,
        version=document.review_version,
        reason=rejection_reason,
        metadata={"decision": review_status.value},
    )
    await session.commit()
    await session.refresh(document)
    return document


async def list_pending_garage_vehicle_links(session: AsyncSession):
    rows = (
        await session.execute(
            select(Vehicle, VehicleUser)
            .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
            .where(VehicleUser.garage_status == GarageValidationStatus.UNDER_REVIEW)
            .order_by(VehicleUser.submitted_for_review_at, VehicleUser.id)
        )
    ).all()
    return [await build_admin_garage_vehicle_link_read(session, *row) for row in rows]


async def review_garage_vehicle_link(
    session,
    vehicle_link_id,
    verification_status,
    verification_rejection_reason,
    *,
    actor,
    expected_version,
):
    vehicle, link = await locked_vehicle_link(session, vehicle_link_id)
    check_review(actor, link, expected_version)
    if verification_status == VerificationStatus.VERIFIED:
        checklist = await build_document_checklist(session, link)
        if link.garage_status != GarageValidationStatus.UNDER_REVIEW or any(
            kind not in checklist.approved for kind in checklist.required
        ):
            raise HTTPException(
                status_code=409, detail="All required documents must be approved before activation"
            )
        link.verification_status = VerificationStatus.VERIFIED
        link.garage_status = GarageValidationStatus.ACTIVE
        link.verification_rejection_reason = None
    elif verification_status == VerificationStatus.REJECTED:
        if not (verification_rejection_reason or "").strip():
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        link.verification_status = VerificationStatus.REJECTED
        link.garage_status = GarageValidationStatus.REJECTED
        link.verification_rejection_reason = verification_rejection_reason
        link.review_attempts += 1
    else:
        raise HTTPException(status_code=400, detail="Review status must be verified or rejected")
    link.reviewed_at = datetime.now(UTC)
    link.review_version += 1
    await append_audit(
        session,
        actor_id=actor.id,
        action="vehicle_link.review",
        target_type="vehicle_link",
        target_id=link.id,
        version=link.review_version,
        reason=verification_rejection_reason,
        metadata={"decision": verification_status.value},
    )
    await session.commit()
    await session.refresh(link)
    return await build_admin_garage_vehicle_link_read(session, vehicle, link)


async def request_garage_additional_documents(
    session, vehicle_link_id, payload: AdminAdditionalDocumentsRequest, *, actor
):
    vehicle, link = await locked_vehicle_link(session, vehicle_link_id)
    check_review(actor, link, payload.expected_version)
    link.requested_document_types = sorted(
        set(link.requested_document_types or [])
        | {kind.value for kind in payload.requested_document_types}
    )
    link.admin_review_note = payload.note
    link.garage_status = GarageValidationStatus.PENDING_DOCUMENTS
    link.verification_status = VerificationStatus.PENDING
    link.review_version += 1
    await append_audit(
        session,
        actor_id=actor.id,
        action="vehicle_link.request_documents",
        target_type="vehicle_link",
        target_id=link.id,
        version=link.review_version,
        reason=payload.note,
        metadata={"requested_document_types": link.requested_document_types},
    )
    await session.commit()
    await session.refresh(link)
    return await build_admin_garage_vehicle_link_read(session, vehicle, link)
