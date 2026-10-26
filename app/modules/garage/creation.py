from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.garage.policy import lock_garage
from app.modules.garage.schemas import GarageVehicleCreate
from app.modules.users.models import User
from app.modules.vehicles.models import (
    GarageMembership,
    GarageValidationStatus,
    Vehicle,
    VehicleUser,
    VerificationStatus,
)


async def create_garage_vehicle_link(
    session: AsyncSession,
    payload: GarageVehicleCreate,
    user: User,
) -> tuple[Vehicle, VehicleUser]:
    await lock_garage(session, user.id)
    await session.refresh(user)
    vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == payload.plate))
    if vehicle is not None:
        existing = await session.scalar(
            select(VehicleUser).where(
                VehicleUser.user_id == user.id,
                VehicleUser.vehicle_id == vehicle.id,
            )
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Vehicle already in garage")
        if (vehicle.chassis is not None and vehicle.chassis != payload.chassis) or (
            vehicle.renavam is not None and vehicle.renavam != payload.renavam
        ):
            raise HTTPException(status_code=409, detail="Vehicle identifiers require review")
    else:
        duplicate = await session.scalar(
            select(Vehicle.id).where(
                or_(
                    Vehicle.chassis == payload.chassis,
                    Vehicle.renavam == payload.renavam,
                )
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Vehicle identifiers already registered")
        vehicle = Vehicle(**payload.model_dump(exclude={"relationship_type", "relationship_note"}))
        session.add(vehicle)
    try:
        await session.flush()
        link = VehicleUser(
            vehicle_id=vehicle.id,
            user_id=user.id,
            relationship_type=payload.relationship_type,
            relationship_note=payload.relationship_note,
            verification_status=VerificationStatus.PENDING,
            garage_status=GarageValidationStatus.PENDING_DOCUMENTS,
            review_attempts=0,
            declared_vehicle_data=payload.model_dump(
                mode="json", exclude={"relationship_type", "relationship_note"}
            ),
        )
        session.add(link)
        session.add(GarageMembership(vehicle_id=vehicle.id, user_id=user.id))
        if user.free_garage_vehicle_id is None:
            user.free_garage_vehicle_id = vehicle.id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Vehicle identifiers already registered"
        ) from exc
    await session.refresh(vehicle)
    await session.refresh(link)
    return vehicle, link
