from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.vehicles.schemas import VehicleCreate, VehicleRead
from app.modules.vehicles.service import (
    create_vehicle_for_user,
    get_user_vehicle,
    list_user_vehicles,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleRead:
    return await create_vehicle_for_user(session, payload, current_user)


@router.get("", response_model=list[VehicleRead])
async def list_vehicles(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[VehicleRead]:
    return await list_user_vehicles(session, current_user)


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def read_vehicle(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleRead:
    return await get_user_vehicle(session, vehicle_id, current_user)
