from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.maintenance.schemas import (
    MaintenanceRecordCreate,
    MaintenanceRecordRead,
    MaintenanceRecordUpdate,
)
from app.modules.maintenance.service import (
    create_maintenance_record,
    get_maintenance_record,
    list_vehicle_maintenance_records,
    update_maintenance_record,
)
from app.modules.users.models import User

router = APIRouter(tags=["maintenance"])


@router.post(
    "/vehicles/{vehicle_id}/maintenance-records",
    response_model=MaintenanceRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_maintenance_record(
    vehicle_id: int,
    payload: MaintenanceRecordCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await create_maintenance_record(session, vehicle_id, payload, current_user)


@router.get(
    "/vehicles/{vehicle_id}/maintenance-records",
    response_model=list[MaintenanceRecordRead],
)
async def read_vehicle_maintenance_records(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MaintenanceRecordRead]:
    return await list_vehicle_maintenance_records(session, vehicle_id, current_user)


@router.get("/maintenance-records/{record_id}", response_model=MaintenanceRecordRead)
async def read_maintenance_record(
    record_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await get_maintenance_record(session, record_id, current_user)


@router.patch("/maintenance-records/{record_id}", response_model=MaintenanceRecordRead)
async def patch_maintenance_record(
    record_id: int,
    payload: MaintenanceRecordUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await update_maintenance_record(session, record_id, payload, current_user)
