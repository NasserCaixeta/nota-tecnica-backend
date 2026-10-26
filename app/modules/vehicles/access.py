from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus


async def require_vehicle_link(
    session: AsyncSession,
    user_id: int,
    vehicle_id: int,
) -> VehicleUser:
    link = await session.scalar(
        select(VehicleUser).where(
            VehicleUser.user_id == user_id,
            VehicleUser.vehicle_id == vehicle_id,
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return link


async def require_active_vehicle_link(
    session: AsyncSession,
    user_id: int,
    vehicle_id: int,
) -> VehicleUser:
    link = await require_vehicle_link(session, user_id, vehicle_id)
    if link.verification_status != VerificationStatus.VERIFIED or (
        link.garage_status != GarageValidationStatus.ACTIVE
    ):
        raise HTTPException(status_code=403, detail="A validated vehicle relationship is required")
    return link
