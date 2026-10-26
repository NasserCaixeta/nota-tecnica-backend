from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.vehicles.models import (
    Vehicle,
    VehicleUser,
)
from app.modules.vehicles.schemas import VehicleCreate, VehicleRead


def build_vehicle_read(vehicle: Vehicle, link: VehicleUser) -> VehicleRead:
    data = link.declared_vehicle_data or {}
    return VehicleRead(
        id=vehicle.id,
        vehicle_link_id=link.id,
        plate=vehicle.plate,
        brand=data.get("brand", vehicle.brand),
        model=data.get("model", vehicle.model),
        model_year=data.get("model_year", vehicle.model_year),
        color=data.get("color", vehicle.color),
        vehicle_type=data.get("vehicle_type", vehicle.vehicle_type),
        chassis=data.get("chassis", vehicle.chassis),
        renavam=data.get("renavam", vehicle.renavam),
        fuel_type=data.get("fuel_type", vehicle.fuel_type),
        engine=data.get("engine", vehicle.engine),
        transmission=data.get("transmission", vehicle.transmission),
        relationship_type=link.relationship_type,
        verification_status=link.verification_status,
        verification_rejection_reason=link.verification_rejection_reason,
        garage_status=link.garage_status,
        relationship_note=link.relationship_note,
        review_attempts=link.review_attempts,
        submitted_for_review_at=link.submitted_for_review_at,
        reviewed_at=link.reviewed_at,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


async def create_vehicle_for_user(
    session: AsyncSession,
    payload: VehicleCreate,
    user: User,
) -> VehicleRead:
    from app.modules.garage.creation import create_garage_vehicle_link
    from app.modules.garage.schemas import GarageVehicleCreate

    vehicle, link = await create_garage_vehicle_link(
        session, GarageVehicleCreate(**payload.model_dump()), user
    )
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
