from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentUploadStatus, ValidationDocumentType
from app.modules.garage.requirements import required_documents_for_relationship
from app.modules.garage.schemas import (
    AdminGarageVehicleLinkRead,
    GarageDashboard,
    GarageDocumentChecklist,
    GaragePermissions,
    GarageRecommendedWorkshop,
    GarageRelationshipUpdate,
    GarageReviewSubmitResponse,
    GarageSummary,
    GarageVehicleCreate,
    GarageVehicleItem,
)
from app.modules.ranking.service import list_workshop_ranking
from app.modules.users.models import User
from app.modules.vehicles.models import (
    GarageValidationStatus,
    Vehicle,
    VehicleUser,
    VerificationStatus,
)


def build_garage_permissions(
    garage_status: GarageValidationStatus,
    *,
    can_submit_review: bool,
) -> GaragePermissions:
    if garage_status == GarageValidationStatus.PAYMENT_REQUIRED:
        return GaragePermissions(
            can_add_maintenance=False,
            can_upload_documents=False,
            can_submit_review=False,
            can_share_history=False,
            can_generate_sale_report=False,
        )
    if garage_status == GarageValidationStatus.REJECTED:
        return GaragePermissions(
            can_add_maintenance=False,
            can_upload_documents=True,
            can_submit_review=can_submit_review,
            can_share_history=False,
            can_generate_sale_report=False,
        )
    if garage_status == GarageValidationStatus.ACTIVE:
        return GaragePermissions(
            can_add_maintenance=True,
            can_upload_documents=False,
            can_submit_review=False,
            can_share_history=True,
            can_generate_sale_report=True,
        )
    if garage_status == GarageValidationStatus.UNDER_REVIEW:
        return GaragePermissions(
            can_add_maintenance=True,
            can_upload_documents=False,
            can_submit_review=False,
            can_share_history=False,
            can_generate_sale_report=False,
        )
    return GaragePermissions(
        can_add_maintenance=True,
        can_upload_documents=True,
        can_submit_review=can_submit_review,
        can_share_history=False,
        can_generate_sale_report=False,
    )


async def user_has_free_vehicle_slot(session: AsyncSession, user: User) -> bool:
    result = await session.execute(
        select(VehicleUser).where(
            VehicleUser.user_id == user.id,
            VehicleUser.garage_status != GarageValidationStatus.PAYMENT_REQUIRED,
        )
    )
    return result.first() is None


async def find_vehicle_by_unique_fields(
    session: AsyncSession,
    payload: GarageVehicleCreate,
) -> Vehicle | None:
    result = await session.execute(select(Vehicle).where(Vehicle.plate == payload.plate))
    return result.scalar_one_or_none()


async def create_garage_vehicle(
    session: AsyncSession,
    payload: GarageVehicleCreate,
    user: User,
) -> GarageVehicleItem:
    vehicle = await find_vehicle_by_unique_fields(session, payload)
    if vehicle is None:
        vehicle = Vehicle(
            plate=payload.plate,
            brand=payload.brand,
            model=payload.model,
            model_year=payload.model_year,
            color=payload.color,
            vehicle_type=payload.vehicle_type,
            chassis=payload.chassis,
            renavam=payload.renavam,
            fuel_type=payload.fuel_type,
            engine=payload.engine,
            transmission=payload.transmission,
        )
        session.add(vehicle)
        await session.flush()
    else:
        existing_link = await session.execute(
            select(VehicleUser).where(
                VehicleUser.vehicle_id == vehicle.id,
                VehicleUser.user_id == user.id,
            )
        )
        if existing_link.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle already in garage",
            )

    garage_status = (
        GarageValidationStatus.PENDING_DOCUMENTS
        if await user_has_free_vehicle_slot(session, user)
        else GarageValidationStatus.PAYMENT_REQUIRED
    )
    link = VehicleUser(
        vehicle_id=vehicle.id,
        user_id=user.id,
        relationship_type=payload.relationship_type,
        relationship_note=payload.relationship_note,
        verification_status=VerificationStatus.PENDING,
        garage_status=garage_status,
        review_attempts=0,
    )
    session.add(link)
    await session.commit()
    await session.refresh(vehicle)
    await session.refresh(link)
    return await build_garage_vehicle_item(session, vehicle, link)


async def uploaded_validation_document_types(
    session: AsyncSession,
    link: VehicleUser,
) -> list[ValidationDocumentType]:
    result = await session.execute(
        select(Document.validation_document_type).where(
            Document.vehicle_link_id == link.id,
            Document.upload_status == DocumentUploadStatus.UPLOADED,
            Document.validation_document_type.is_not(None),
        )
    )
    return [value for value in result.scalars().all() if value is not None]


async def build_document_checklist(
    session: AsyncSession,
    link: VehicleUser,
) -> GarageDocumentChecklist:
    base_required = required_documents_for_relationship(link.relationship_type)
    extra_required = [
        ValidationDocumentType(value)
        for value in (link.requested_document_types or [])
        if ValidationDocumentType(value) not in base_required
    ]
    required = [*base_required, *extra_required]
    uploaded = await uploaded_validation_document_types(session, link)
    missing = [document_type for document_type in required if document_type not in uploaded]
    return GarageDocumentChecklist(required=required, uploaded=uploaded, missing=missing)


async def build_recommended_workshops(
    session: AsyncSession,
    limit: int = 3,
) -> list[GarageRecommendedWorkshop]:
    ranking = await list_workshop_ranking(
        session,
        city=None,
        state=None,
        category=None,
        limit=limit,
    )
    return [
        GarageRecommendedWorkshop(
            workshop_id=item.workshop_id,
            trade_name=item.trade_name,
            city=item.city,
            state=item.state,
            score=item.score,
        )
        for item in ranking.items
    ]


async def build_garage_vehicle_item(
    session: AsyncSession,
    vehicle: Vehicle,
    link: VehicleUser,
) -> GarageVehicleItem:
    checklist = await build_document_checklist(session, link)
    can_submit_review = not checklist.missing and link.garage_status in {
        GarageValidationStatus.PENDING_DOCUMENTS,
        GarageValidationStatus.REJECTED,
    }
    return GarageVehicleItem(
        vehicle_id=vehicle.id,
        vehicle_link_id=link.id,
        plate=vehicle.plate,
        brand=vehicle.brand,
        model=vehicle.model,
        model_year=vehicle.model_year,
        relationship_type=link.relationship_type,
        garage_status=link.garage_status,
        verification_rejection_reason=link.verification_rejection_reason,
        review_attempts=link.review_attempts,
        permissions=build_garage_permissions(
            link.garage_status,
            can_submit_review=can_submit_review,
        ),
        documents=checklist,
        maintenance_alerts=[],
        recommended_workshops=await build_recommended_workshops(session),
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


async def list_garage_vehicle_items(session: AsyncSession, user: User) -> list[GarageVehicleItem]:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.user_id == user.id)
        .order_by(Vehicle.id)
    )
    return [
        await build_garage_vehicle_item(session, vehicle, link)
        for vehicle, link in result.all()
    ]


def build_garage_summary(items: list[GarageVehicleItem]) -> GarageSummary:
    return GarageSummary(
        total=len(items),
        pending_documents=sum(
            1 for item in items if item.garage_status == GarageValidationStatus.PENDING_DOCUMENTS
        ),
        under_review=sum(
            1 for item in items if item.garage_status == GarageValidationStatus.UNDER_REVIEW
        ),
        active=sum(1 for item in items if item.garage_status == GarageValidationStatus.ACTIVE),
        rejected=sum(1 for item in items if item.garage_status == GarageValidationStatus.REJECTED),
        payment_required=sum(
            1 for item in items if item.garage_status == GarageValidationStatus.PAYMENT_REQUIRED
        ),
        has_free_vehicle_slot=not any(
            item.garage_status != GarageValidationStatus.PAYMENT_REQUIRED for item in items
        ),
    )


async def get_garage_dashboard(session: AsyncSession, user: User) -> GarageDashboard:
    items = await list_garage_vehicle_items(session, user)
    return GarageDashboard(summary=build_garage_summary(items), vehicles=items)


async def get_garage_vehicle(
    session: AsyncSession,
    vehicle_id: int,
    user: User,
) -> GarageVehicleItem:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(Vehicle.id == vehicle_id, VehicleUser.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    vehicle, link = row
    return await build_garage_vehicle_item(session, vehicle, link)


async def get_user_vehicle_link(
    session: AsyncSession,
    vehicle_link_id: int,
    user: User,
) -> tuple[Vehicle, VehicleUser]:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.id == vehicle_link_id, VehicleUser.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle link not found")
    return row


async def update_garage_relationship(
    session: AsyncSession,
    vehicle_link_id: int,
    payload: GarageRelationshipUpdate,
    user: User,
) -> GarageVehicleItem:
    vehicle, link = await get_user_vehicle_link(session, vehicle_link_id, user)
    if link.garage_status in {GarageValidationStatus.UNDER_REVIEW, GarageValidationStatus.ACTIVE}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relationship cannot be changed in the current garage status",
        )
    if link.garage_status == GarageValidationStatus.PAYMENT_REQUIRED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment required")
    link.relationship_type = payload.relationship_type
    link.relationship_note = payload.relationship_note
    await session.commit()
    await session.refresh(link)
    return await build_garage_vehicle_item(session, vehicle, link)


async def submit_garage_vehicle_review(
    session: AsyncSession,
    vehicle_link_id: int,
    user: User,
) -> GarageReviewSubmitResponse:
    _, link = await get_user_vehicle_link(session, vehicle_link_id, user)
    if link.garage_status == GarageValidationStatus.PAYMENT_REQUIRED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment required")
    if link.garage_status not in {
        GarageValidationStatus.PENDING_DOCUMENTS,
        GarageValidationStatus.REJECTED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle link cannot be submitted in the current status",
        )
    checklist = await build_document_checklist(session, link)
    if checklist.missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required validation documents are missing",
        )
    link.garage_status = GarageValidationStatus.UNDER_REVIEW
    link.submitted_for_review_at = datetime.now(UTC)
    link.verification_rejection_reason = None
    await session.commit()
    await session.refresh(link)
    return GarageReviewSubmitResponse(
        vehicle_link_id=link.id,
        garage_status=link.garage_status,
        missing_documents=[],
    )


async def build_admin_garage_vehicle_link_read(
    session: AsyncSession,
    vehicle: Vehicle,
    link: VehicleUser,
) -> AdminGarageVehicleLinkRead:
    checklist = await build_document_checklist(session, link)
    return AdminGarageVehicleLinkRead(
        vehicle_link_id=link.id,
        vehicle_id=vehicle.id,
        user_id=link.user_id,
        plate=vehicle.plate,
        relationship_type=link.relationship_type,
        garage_status=link.garage_status,
        required_documents=checklist.required,
        uploaded_documents=checklist.uploaded,
        missing_documents=checklist.missing,
        verification_rejection_reason=link.verification_rejection_reason,
        review_attempts=link.review_attempts,
        submitted_for_review_at=link.submitted_for_review_at,
        reviewed_at=link.reviewed_at,
    )
