from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.admin.participation import review_participant, set_admin_access
from app.modules.admin.schemas import AdminAccessUpdate, ParticipantReview
from app.modules.admin.service import (
    list_pending_garage_vehicle_links,
    request_garage_additional_documents,
    review_document,
    review_garage_vehicle_link,
    review_vehicle_link,
)
from app.modules.auth.dependencies import get_current_admin_user
from app.modules.documents.models import DocumentReviewStatus
from app.modules.documents.schemas import DocumentRead
from app.modules.garage.schemas import AdminAdditionalDocumentsRequest, AdminGarageVehicleLinkRead
from app.modules.users.models import ParticipationStatus, User
from app.modules.users.schemas import UserRead
from app.modules.users.service import user_to_read
from app.modules.vehicles.models import VerificationStatus

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
    verification_status: VerificationStatus
    verification_rejection_reason: str | None = Field(default=None, max_length=500)


class VehicleLinkReviewRead(BaseModel):
    id: int
    vehicle_id: int
    user_id: int
    verification_status: VerificationStatus
    verification_rejection_reason: str | None


class DocumentReviewUpdate(BaseModel):
    review_status: DocumentReviewStatus
    rejection_reason: str | None = Field(default=None, max_length=1000)


@router.patch(
    "/vehicle-links/{vehicle_link_id}/verification",
    response_model=VehicleLinkReviewRead,
)
async def patch_vehicle_link_verification(
    vehicle_link_id: int,
    payload: VehicleLinkReviewUpdate,
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleLinkReviewRead:
    return await review_vehicle_link(
        session,
        vehicle_link_id,
        payload.verification_status,
        payload.verification_rejection_reason,
    )


@router.patch("/documents/{document_id}/review", response_model=DocumentRead)
async def patch_document_review(
    document_id: int,
    payload: DocumentReviewUpdate,
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    return await review_document(
        session,
        document_id,
        payload.review_status,
        payload.rejection_reason,
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
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminGarageVehicleLinkRead:
    return await review_garage_vehicle_link(
        session,
        vehicle_link_id,
        payload.verification_status,
        payload.verification_rejection_reason,
    )


@router.post(
    "/garage/vehicle-links/{vehicle_link_id}/requested-documents",
    response_model=AdminGarageVehicleLinkRead,
)
async def post_garage_additional_documents_request(
    vehicle_link_id: int,
    payload: AdminAdditionalDocumentsRequest,
    _: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminGarageVehicleLinkRead:
    return await request_garage_additional_documents(session, vehicle_link_id, payload)
