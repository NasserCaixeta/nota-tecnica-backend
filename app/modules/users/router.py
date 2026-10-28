from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.audit.service import append_audit
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import ParticipationStatus, User
from app.modules.users.requests import (
    AccountRequest,
    AccountRequestCreate,
    AccountRequestRead,
    create_account_request,
)
from app.modules.users.schemas import UserProfileUpdate, UserRead
from app.modules.users.service import user_to_read

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    return await user_to_read(session, current_user)


@router.post("/me/resubmit-participation", response_model=UserRead)
async def resubmit_participation(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    version = current_user.participation_version
    result = await session.execute(
        update(User)
        .where(
            User.id == current_user.id,
            User.participation_version == version,
            User.participation_status == ParticipationStatus.REJECTED,
        )
        .values(participation_status=ParticipationStatus.PENDING, participation_version=version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="Only a rejected request can be resubmitted")
    await append_audit(
        session,
        actor_id=current_user.id,
        action="participant.resubmit",
        target_type="user",
        target_id=current_user.id,
        version=version + 1,
    )
    await session.commit()
    await session.refresh(current_user)
    return await user_to_read(session, current_user)


@router.patch("/me", response_model=UserRead)
async def update_current_profile(
    payload: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus
    from app.modules.workshops.models import WorkshopClaim, WorkshopUser

    await session.refresh(current_user, with_for_update=True)
    updates = payload.model_dump(exclude_unset=True)
    if "full_name" in updates and updates["full_name"] != current_user.full_name:
        verified_link = await session.scalar(
            select(VehicleUser.id)
            .where(
                VehicleUser.user_id == current_user.id,
                or_(
                    VehicleUser.verification_status == VerificationStatus.VERIFIED,
                    VehicleUser.garage_status == GarageValidationStatus.UNDER_REVIEW,
                ),
            )
            .limit(1)
        )
        claim = await session.scalar(
            select(WorkshopClaim.id)
            .where(
                WorkshopClaim.user_id == current_user.id,
                WorkshopClaim.status.in_((VerificationStatus.PENDING, VerificationStatus.VERIFIED)),
            )
            .limit(1)
        )
        representation = await session.scalar(
            select(WorkshopUser.id)
            .where(
                WorkshopUser.user_id == current_user.id,
                WorkshopUser.verification_status == VerificationStatus.VERIFIED,
            )
            .limit(1)
        )
        if verified_link is not None or claim is not None or representation is not None:
            raise HTTPException(
                status_code=409, detail="Identity changes require administrative review"
            )
        current_user.participation_version += 1
    for field, value in updates.items():
        setattr(current_user, field, value)
    await append_audit(
        session,
        actor_id=current_user.id,
        action="profile.update",
        target_type="user",
        target_id=current_user.id,
        metadata={"fields": sorted(updates)},
    )
    await session.commit()
    await session.refresh(current_user)
    return await user_to_read(session, current_user)


@router.post("/me/closure-requests", response_model=AccountRequestRead, status_code=201)
async def request_account_closure(
    payload: AccountRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_account_request(session, current_user, "closure", payload.reason)


@router.get("/me/closure-requests", response_model=list[AccountRequestRead])
async def own_closure_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return list(
        (
            await session.scalars(
                select(AccountRequest)
                .where(AccountRequest.user_id == current_user.id, AccountRequest.kind == "closure")
                .order_by(AccountRequest.id.desc())
            )
        ).all()
    )


@router.post("/me/identity-requests", response_model=AccountRequestRead, status_code=201)
async def request_identity_correction(
    payload: AccountRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_account_request(
        session, current_user, "identity_correction", payload.reason
    )


@router.get("/me/identity-requests", response_model=list[AccountRequestRead])
async def own_identity_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return list(
        (
            await session.scalars(
                select(AccountRequest)
                .where(
                    AccountRequest.user_id == current_user.id,
                    AccountRequest.kind == "identity_correction",
                )
                .order_by(AccountRequest.id.desc())
            )
        ).all()
    )
