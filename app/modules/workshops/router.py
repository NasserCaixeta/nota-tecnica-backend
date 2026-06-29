from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.workshops.schemas import ManagedWorkshopRead, WorkshopCreate, WorkshopRead
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
    current_user: Annotated[User, Depends(get_current_user)],
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
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ManagedWorkshopRead]:
    return await list_managed_workshops(session, current_user)


@router.get("/{workshop_id}", response_model=WorkshopRead)
async def read_workshop(
    workshop_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkshopRead:
    return await get_workshop(session, workshop_id)
