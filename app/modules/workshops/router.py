from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validators import validate_cnpj
from app.db.session import get_db
from app.modules.auth.dependencies import get_approved_participant
from app.modules.users.models import User
from app.modules.workshops.claims import claim_to_read, create_workshop_claim
from app.modules.workshops.models import Workshop, WorkshopClaim
from app.modules.workshops.schemas import (
    ManagedWorkshopRead,
    WorkshopClaimRead,
    WorkshopCreate,
    WorkshopRead,
)
from app.modules.workshops.service import (
    create_workshop_for_user,
    get_workshop,
    list_managed_workshops,
    list_workshops,
)

router = APIRouter(prefix="/workshops", tags=["workshops"])


@router.post("", response_model=WorkshopRead, status_code=status.HTTP_201_CREATED)
async def create_workshop(
    payload: WorkshopCreate,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkshopRead:
    return await create_workshop_for_user(session, payload, current_user)


@router.get("", response_model=list[WorkshopRead])
async def read_workshops(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkshopRead]:
    return await list_workshops(session)


@router.get("/me", response_model=list[ManagedWorkshopRead])
async def read_managed_workshops(
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ManagedWorkshopRead]:
    return await list_managed_workshops(session, current_user)


@router.get("/claims/me", response_model=list[WorkshopClaimRead])
async def my_workshop_claims(
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    claims = (
        await session.scalars(
            select(WorkshopClaim)
            .where(WorkshopClaim.user_id == actor.id)
            .order_by(WorkshopClaim.id.desc())
        )
    ).all()
    return [await claim_to_read(session, claim) for claim in claims]


@router.get("/lookup")
async def lookup_workshop(
    cnpj: str,
    _: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        normalized = validate_cnpj(cnpj)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid CNPJ") from exc
    office = await session.scalar(select(Workshop).where(Workshop.cnpj == normalized))
    if office is None:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return {
        "id": office.id,
        "trade_name": office.trade_name,
        "cnpj": office.cnpj,
        "verification_status": office.verification_status,
    }


@router.post("/{workshop_id}/claims", response_model=WorkshopClaimRead, status_code=201)
async def request_workshop_claim(
    workshop_id: int,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    claim = await create_workshop_claim(session, workshop_id, actor)
    return await claim_to_read(session, claim)


@router.get("/{workshop_id}", response_model=WorkshopRead)
async def read_workshop(
    workshop_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkshopRead:
    return await get_workshop(session, workshop_id)
