from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.schemas import MaintenanceRecordCreate, MaintenanceRecordUpdate
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle, VehicleUser
from app.modules.workshops.models import Workshop


async def ensure_user_vehicle_link(session: AsyncSession, vehicle_id: int, user: User) -> Vehicle:
    result = await session.execute(
        select(Vehicle)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(Vehicle.id == vehicle_id, VehicleUser.user_id == user.id)
    )
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


async def ensure_workshop_exists(session: AsyncSession, workshop_id: int | None) -> None:
    if workshop_id is None:
        return
    workshop = await session.get(Workshop, workshop_id)
    if workshop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop not found")


def calculate_total(labor_cost: Decimal, parts_cost: Decimal) -> Decimal:
    return labor_cost + parts_cost


async def create_maintenance_record(
    session: AsyncSession,
    vehicle_id: int,
    payload: MaintenanceRecordCreate,
    user: User,
) -> MaintenanceRecord:
    await ensure_user_vehicle_link(session, vehicle_id, user)
    await ensure_workshop_exists(session, payload.workshop_id)
    record = MaintenanceRecord(
        **payload.model_dump(),
        vehicle_id=vehicle_id,
        author_user_id=user.id,
        total_cost=calculate_total(payload.labor_cost, payload.parts_cost),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_vehicle_maintenance_records(
    session: AsyncSession,
    vehicle_id: int,
    user: User,
) -> list[MaintenanceRecord]:
    await ensure_user_vehicle_link(session, vehicle_id, user)
    result = await session.execute(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.vehicle_id == vehicle_id)
        .order_by(MaintenanceRecord.service_date.desc(), MaintenanceRecord.id.desc())
    )
    return list(result.scalars().all())


async def get_maintenance_record(
    session: AsyncSession,
    record_id: int,
    user: User,
) -> MaintenanceRecord:
    record = await session.get(MaintenanceRecord, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance record not found",
        )
    await ensure_user_vehicle_link(session, record.vehicle_id, user)
    return record


async def update_maintenance_record(
    session: AsyncSession,
    record_id: int,
    payload: MaintenanceRecordUpdate,
    user: User,
) -> MaintenanceRecord:
    record = await get_maintenance_record(session, record_id, user)
    if record.author_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the maintenance author can update this record",
        )
    updates = payload.model_dump(exclude_unset=True)
    if "workshop_id" in updates:
        await ensure_workshop_exists(session, updates["workshop_id"])
    for field, value in updates.items():
        setattr(record, field, value)
    record.total_cost = calculate_total(record.labor_cost, record.parts_cost)
    await session.commit()
    await session.refresh(record)
    return record
