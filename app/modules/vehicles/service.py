from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.vehicles.models import (
    Vehicle,
    VehicleRelationshipType,
    VehicleUser,
    VerificationStatus,
)
from app.modules.vehicles.schemas import VehicleCreate, VehicleRead


def build_vehicle_read(vehicle: Vehicle, link: VehicleUser) -> VehicleRead:
    return VehicleRead(
        id=vehicle.id,
        plate=vehicle.plate,
        brand=vehicle.brand,
        model=vehicle.model,
        model_year=vehicle.model_year,
        color=vehicle.color,
        vehicle_type=vehicle.vehicle_type,
        chassis=vehicle.chassis,
        renavam=vehicle.renavam,
        fuel_type=vehicle.fuel_type,
        engine=vehicle.engine,
        transmission=vehicle.transmission,
        relationship_type=link.relationship_type,
        verification_status=link.verification_status,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


async def create_vehicle_for_user(
    session: AsyncSession,
    payload: VehicleCreate,
    user: User,
) -> VehicleRead:
    plate_result = await session.execute(select(Vehicle).where(Vehicle.plate == payload.plate))
    if plate_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle plate already registered",
        )

    chassis_result = await session.execute(
        select(Vehicle).where(Vehicle.chassis == payload.chassis)
    )
    if chassis_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle chassis already registered",
        )

    renavam_result = await session.execute(
        select(Vehicle).where(Vehicle.renavam == payload.renavam)
    )
    if renavam_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle Renavam already registered",
        )

    vehicle = Vehicle(**payload.model_dump())
    session.add(vehicle)
    await session.flush()

    link = VehicleUser(
        vehicle_id=vehicle.id,
        user_id=user.id,
        relationship_type=VehicleRelationshipType.OWNER,
        verification_status=VerificationStatus.PENDING,
    )
    session.add(link)
    await session.commit()
    await session.refresh(vehicle)

    return build_vehicle_read(vehicle, link)


async def list_user_vehicles(session: AsyncSession, user: User) -> list[VehicleRead]:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(VehicleUser.user_id == user.id)
        .order_by(Vehicle.id)
    )
    return [build_vehicle_read(vehicle, link) for vehicle, link in result.all()]


async def get_user_vehicle(session: AsyncSession, vehicle_id: int, user: User) -> VehicleRead:
    result = await session.execute(
        select(Vehicle, VehicleUser)
        .join(VehicleUser, VehicleUser.vehicle_id == Vehicle.id)
        .where(Vehicle.id == vehicle_id, VehicleUser.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    vehicle, link = row
    return build_vehicle_read(vehicle, link)
