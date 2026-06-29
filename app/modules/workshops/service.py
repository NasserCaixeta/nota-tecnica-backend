from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserProfileType
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.models import (
    Workshop,
    WorkshopSource,
    WorkshopUser,
    WorkshopUserRole,
)
from app.modules.workshops.schemas import ManagedWorkshopRead, WorkshopCreate, WorkshopRead


def workshop_to_read(workshop: Workshop) -> WorkshopRead:
    return WorkshopRead(
        id=workshop.id,
        legal_name=workshop.legal_name,
        trade_name=workshop.trade_name,
        cnpj=workshop.cnpj,
        phone=workshop.phone,
        email=workshop.email,
        zip_code=workshop.zip_code,
        street=workshop.street,
        number=workshop.number,
        neighborhood=workshop.neighborhood,
        city=workshop.city,
        state=workshop.state,
        complement=workshop.complement,
        specialties=workshop.specialties,
        source=workshop.source,
        verification_status=workshop.verification_status,
        created_at=workshop.created_at,
        updated_at=workshop.updated_at,
    )


async def create_workshop_for_user(
    session: AsyncSession,
    payload: WorkshopCreate,
    user: User,
) -> WorkshopRead:
    result = await session.execute(select(Workshop).where(Workshop.cnpj == payload.cnpj))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workshop CNPJ already registered",
        )

    if (
        payload.source == WorkshopSource.OWNER_CLAIMED
        and user.profile_type != UserProfileType.WORKSHOP_OWNER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workshop owners can claim a workshop",
        )

    workshop = Workshop(
        legal_name=payload.legal_name,
        trade_name=payload.trade_name,
        cnpj=payload.cnpj,
        phone=payload.phone,
        email=str(payload.email),
        zip_code=payload.zip_code,
        street=payload.street,
        number=payload.number,
        neighborhood=payload.neighborhood,
        city=payload.city,
        state=payload.state,
        complement=payload.complement,
        specialties=payload.specialties,
        source=payload.source,
        verification_status=VerificationStatus.PENDING,
        submitted_by_user_id=user.id if payload.source == WorkshopSource.USER_SUBMITTED else None,
    )
    session.add(workshop)
    await session.flush()

    if payload.source == WorkshopSource.OWNER_CLAIMED:
        session.add(
            WorkshopUser(
                workshop_id=workshop.id,
                user_id=user.id,
                role=WorkshopUserRole.OWNER,
                verification_status=VerificationStatus.PENDING,
            )
        )

    await session.commit()
    await session.refresh(workshop)
    return workshop_to_read(workshop)


async def list_workshops(session: AsyncSession) -> list[WorkshopRead]:
    result = await session.execute(select(Workshop).order_by(Workshop.id))
    return [workshop_to_read(workshop) for workshop in result.scalars().all()]


async def get_workshop(session: AsyncSession, workshop_id: int) -> WorkshopRead:
    workshop = await session.get(Workshop, workshop_id)
    if workshop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop not found")
    return workshop_to_read(workshop)


async def list_managed_workshops(session: AsyncSession, user: User) -> list[ManagedWorkshopRead]:
    result = await session.execute(
        select(Workshop, WorkshopUser)
        .join(WorkshopUser, WorkshopUser.workshop_id == Workshop.id)
        .where(WorkshopUser.user_id == user.id)
        .order_by(Workshop.id)
    )
    return [
        ManagedWorkshopRead(**workshop_to_read(workshop).model_dump(), role=link.role)
        for workshop, link in result.all()
    ]
