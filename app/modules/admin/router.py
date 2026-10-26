from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.admin.participation import review_participant, set_admin_access
from app.modules.admin.schemas import AdminAccessUpdate, ParticipantReview
from app.modules.admin.service import (
    get_admin_garage_vehicle_link,
    list_pending_garage_vehicle_links,
    request_garage_additional_documents,
    review_document,
    review_garage_vehicle_link,
    review_vehicle_link,
)
from app.modules.auth.dependencies import get_current_admin_user
from app.modules.documents.schemas import DocumentRead, DocumentReviewUpdate
from app.modules.garage.schemas import AdminAdditionalDocumentsRequest, AdminGarageVehicleLinkRead
from app.modules.maintenance.disputes import dispute_to_read, review_dispute
from app.modules.maintenance.models import ServiceDispute, ServiceDuplicateProposal
from app.modules.maintenance.moderation import (
    pending_maintenance,
    review_maintenance,
    revision_evidence,
)
from app.modules.maintenance.revisions import record_to_read
from app.modules.maintenance.schemas import (
    MaintenanceRecordRead,
    MaintenanceReview,
    ServiceDisputeReview,
)
from app.modules.maintenance.service import get_maintenance_record
from app.modules.ranking.reviews import ServiceReviewModeration, moderate_service_review
from app.modules.users.models import ParticipationStatus, User
from app.modules.users.schemas import UserRead
from app.modules.users.service import user_to_read
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.schemas import WorkshopClaimReview

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/participants", response_model=list[UserRead])
async def read_participants(
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[
        ParticipationStatus, Query(alias="status")
    ] = ParticipationStatus.PENDING,
) -> list[UserRead]:
    users = (
        await session.scalars(
            select(User)
            .where(User.participation_status == status_filter)
            .order_by(User.created_at, User.id)
        )
    ).all()
    return [await user_to_read(session, user) for user in users]


@router.patch("/participants/{user_id}/review", response_model=UserRead)
async def patch_participant_review(
    user_id: int,
    payload: ParticipantReview,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    user = await review_participant(session, actor=actor, user_id=user_id, **payload.model_dump())
    return await user_to_read(session, user)


@router.patch("/users/{user_id}/admin-access", response_model=UserRead)
async def patch_admin_access(
    user_id: int,
    payload: AdminAccessUpdate,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    user = await set_admin_access(session, actor=actor, user_id=user_id, **payload.model_dump())
    return await user_to_read(session, user)


class VehicleLinkReviewUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    verification_status: VerificationStatus
    verification_rejection_reason: str | None = Field(default=None, max_length=500)


class VehicleLinkReviewRead(BaseModel):
    id: int
    vehicle_id: int
    user_id: int
    verification_status: VerificationStatus
    verification_rejection_reason: str | None


@router.patch(
    "/vehicle-links/{vehicle_link_id}/verification",
    response_model=VehicleLinkReviewRead,
)
async def patch_vehicle_link_verification(
    vehicle_link_id: int,
    payload: VehicleLinkReviewUpdate,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleLinkReviewRead:
    return await review_vehicle_link(
        session,
        vehicle_link_id,
        payload.verification_status,
        payload.verification_rejection_reason,
        actor=actor,
        expected_version=payload.expected_version,
    )


@router.patch("/documents/{document_id}/review", response_model=DocumentRead)
async def patch_document_review(
    document_id: int,
    payload: DocumentReviewUpdate,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    return await review_document(
        session,
        document_id,
        payload.review_status,
        payload.rejection_reason,
        actor=actor,
        expected_version=payload.expected_version,
    )


@router.get(
    "/garage/vehicle-links/pending",
    response_model=list[AdminGarageVehicleLinkRead],
)
async def read_pending_garage_vehicle_links(
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminGarageVehicleLinkRead]:
    return await list_pending_garage_vehicle_links(session)


@router.patch(
    "/garage/vehicle-links/{vehicle_link_id}/review",
    response_model=AdminGarageVehicleLinkRead,
)
async def patch_garage_vehicle_link_review(
    vehicle_link_id: int,
    payload: VehicleLinkReviewUpdate,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminGarageVehicleLinkRead:
    return await review_garage_vehicle_link(
        session,
        vehicle_link_id,
        payload.verification_status,
        payload.verification_rejection_reason,
        actor=actor,
        expected_version=payload.expected_version,
    )


@router.post(
    "/garage/vehicle-links/{vehicle_link_id}/requested-documents",
    response_model=AdminGarageVehicleLinkRead,
)
async def post_garage_additional_documents_request(
    vehicle_link_id: int,
    payload: AdminAdditionalDocumentsRequest,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminGarageVehicleLinkRead:
    return await request_garage_additional_documents(session, vehicle_link_id, payload, actor=actor)


@router.get("/garage/vehicle-links/{vehicle_link_id}", response_model=AdminGarageVehicleLinkRead)
async def read_garage_vehicle_link_detail(
    vehicle_link_id: int,
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminGarageVehicleLinkRead:
    return await get_admin_garage_vehicle_link(session, vehicle_link_id)


@router.get("/workshop-claims")
async def read_workshop_claims(
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    from app.modules.workshops.claims import claim_to_read
    from app.modules.workshops.models import WorkshopClaim

    claims = (
        await session.scalars(
            select(WorkshopClaim)
            .where(WorkshopClaim.status == VerificationStatus.PENDING)
            .order_by(WorkshopClaim.created_at, WorkshopClaim.id)
        )
    ).all()
    return [await claim_to_read(session, claim) for claim in claims]


@router.patch("/workshop-claims/{claim_id}/review")
async def patch_workshop_claim(
    claim_id: int,
    payload: WorkshopClaimReview,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    from app.modules.workshops.claims import review_workshop_claim

    return await review_workshop_claim(session, claim_id, payload, actor)


@router.get("/maintenance-reviews", response_model=list[MaintenanceRecordRead])
async def read_maintenance_reviews(
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, r, actor=actor) for r in await pending_maintenance(session)
    ]


@router.get("/maintenance-reviews/{record_id}")
async def read_maintenance_review_detail(
    record_id: int,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    record = await get_maintenance_record(session, record_id, actor)
    result = await record_to_read(session, record, actor=actor)
    documents = await revision_evidence(session, record.current_revision_id)
    return {
        **result.model_dump(mode="json"),
        "documents": [DocumentRead.model_validate(d) for d in documents],
    }


@router.patch("/maintenance-reviews/{record_id}", response_model=MaintenanceRecordRead)
async def patch_maintenance_review(
    record_id: int,
    payload: MaintenanceReview,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await record_to_read(
        session, await review_maintenance(session, record_id, payload, actor), actor=actor
    )


@router.get("/service-disputes")
async def read_service_disputes(
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    items = (
        await session.scalars(
            select(ServiceDispute)
            .where(ServiceDispute.status == "open")
            .order_by(ServiceDispute.id)
        )
    ).all()
    return [await dispute_to_read(session, item, actor) for item in items]


@router.patch("/service-disputes/{dispute_id}")
async def patch_service_dispute(
    dispute_id: int,
    payload: ServiceDisputeReview,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await dispute_to_read(
        session, await review_dispute(session, dispute_id, payload, actor), actor
    )


@router.get("/service-associations")
async def read_service_associations(
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    items = (
        await session.scalars(
            select(ServiceDuplicateProposal)
            .where(ServiceDuplicateProposal.status == "pending")
            .order_by(ServiceDuplicateProposal.id)
        )
    ).all()
    result = []
    for item in items:
        first = await get_maintenance_record(session, item.record_id, actor)
        second = await get_maintenance_record(session, item.other_record_id, actor)
        if first.superseded_by_id is None and second.superseded_by_id is None:
            result.append(
                {
                    "id": item.id,
                    "reason": item.reason,
                    "record": await record_to_read(session, first, actor=actor),
                    "other_record": await record_to_read(session, second, actor=actor),
                }
            )
    return result


@router.patch("/service-reviews/{review_id}")
async def patch_service_review_comment(
    review_id: int,
    payload: ServiceReviewModeration,
    actor: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await moderate_service_review(session, review_id, payload, actor)
