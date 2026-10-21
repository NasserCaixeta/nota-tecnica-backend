from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.audit.service import append_audit
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import ParticipationStatus, User
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
    from app.modules.vehicles.models import VehicleUser, VerificationStatus

    updates = payload.model_dump(exclude_unset=True)
    if "full_name" in updates and updates["full_name"] != current_user.full_name:
        verified_link = await session.scalar(
            select(VehicleUser.id)
            .where(
                VehicleUser.user_id == current_user.id,
                VehicleUser.verification_status == VerificationStatus.VERIFIED,
            )
            .limit(1)
        )
        if verified_link is not None:
            raise HTTPException(
                status_code=409, detail="Identity changes require administrative review"
            )
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
