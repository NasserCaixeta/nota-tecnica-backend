from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import SubscriptionPeriod
from app.modules.users.models import User
from app.modules.vehicles.models import (
    GarageMembership,
    GarageValidationStatus,
    VehicleUser,
    VerificationStatus,
)


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
    active = set(
        (
            await session.scalars(
                select(VehicleUser.vehicle_id).where(
                    VehicleUser.user_id == user_id,
                    VehicleUser.vehicle_id.in_(members),
                    VehicleUser.verification_status == VerificationStatus.VERIFIED,
                    VehicleUser.garage_status == GarageValidationStatus.ACTIVE,
                )
            )
        ).all()
    )
    rejected = set(
        (
            await session.scalars(
                select(VehicleUser.vehicle_id).where(
                    VehicleUser.user_id == user_id,
                    VehicleUser.vehicle_id.in_(members),
                    or_(
                        VehicleUser.verification_status == VerificationStatus.REJECTED,
                        VehicleUser.garage_status == GarageValidationStatus.REJECTED,
                    ),
                )
            )
        ).all()
    )
    eligible = [member for member in members if member not in rejected]
    free_id = user.free_garage_vehicle_id if user else None
    if free_id not in eligible:
        free_id = next(
            (member for member in eligible if member in active), eligible[0] if eligible else None
        )
    subscription = await session.scalar(
        select(SubscriptionPeriod.id)
        .where(
            SubscriptionPeriod.buyer_id == user_id,
            SubscriptionPeriod.revoked_at.is_(None),
            SubscriptionPeriod.starts_at <= now,
            SubscriptionPeriod.expires_at > now,
        )
        .limit(1)
    )
    limit = 5 if subscription is not None else 1
    ordered = ([free_id] if free_id is not None else []) + [
        member for member in eligible if member != free_id
    ]
    return GarageCapacity(
        limit=limit, free_vehicle_id=free_id, writable_vehicle_ids=set(ordered[:limit])
    )


async def require_garage_write(session: AsyncSession, user_id: int, vehicle_id: int) -> None:
    from datetime import UTC

    capacity = await get_garage_capacity(session, user_id, datetime.now(UTC))
    if vehicle_id not in capacity.writable_vehicle_ids:
        raise HTTPException(status_code=403, detail="An active garage subscription is required")
