from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.vehicles.models import GarageMembership


@dataclass(frozen=True)
class GarageCapacity:
    limit: int
    free_vehicle_id: int | None
    writable_vehicle_ids: set[int]


async def lock_garage(session: AsyncSession, user_id: int) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(730042, :user_id)"), {"user_id": user_id}
        )


async def get_garage_capacity(
    session: AsyncSession,
    user_id: int,
    now: datetime,
) -> GarageCapacity:
    user = await session.get(User, user_id, populate_existing=True)
    members = list(
        (
            await session.scalars(
                select(GarageMembership.vehicle_id)
                .where(
                    GarageMembership.user_id == user_id,
                )
                .order_by(GarageMembership.id)
            )
        ).all()
    )
    free_id = user.free_garage_vehicle_id if user else None
    if free_id not in members:
        free_id = members[0] if members else None
    return GarageCapacity(
        limit=1,
        free_vehicle_id=free_id,
        writable_vehicle_ids={free_id} if free_id is not None else set(),
    )


async def require_garage_write(session: AsyncSession, user_id: int, vehicle_id: int) -> None:
    from datetime import UTC

    capacity = await get_garage_capacity(session, user_id, datetime.now(UTC))
    if vehicle_id not in capacity.writable_vehicle_ids:
        raise HTTPException(status_code=403, detail="An active garage subscription is required")
