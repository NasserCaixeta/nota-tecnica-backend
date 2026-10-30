from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import (
    HistoryAccessGrant,
    PaymentOrder,
    SubscriptionCancellation,
    SubscriptionPeriod,
)
from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus


async def active_relationship(session: AsyncSession, user_id: int, vehicle_id: int) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    VehicleUser.user_id == user_id,
                    VehicleUser.vehicle_id == vehicle_id,
                    VehicleUser.verification_status == VerificationStatus.VERIFIED,
                    VehicleUser.garage_status == GarageValidationStatus.ACTIVE,
                )
            )
        )
    )


async def current_history_grant(
    session: AsyncSession, user_id: int, vehicle_id: int, now: datetime
):
    return await session.scalar(
        select(HistoryAccessGrant)
        .where(
            HistoryAccessGrant.buyer_id == user_id,
            HistoryAccessGrant.vehicle_id == vehicle_id,
            HistoryAccessGrant.revoked_at.is_(None),
            HistoryAccessGrant.starts_at <= now,
            HistoryAccessGrant.expires_at > now,
        )
        .order_by(HistoryAccessGrant.expires_at.desc())
        .limit(1)
    )


async def has_history_access(
    session: AsyncSession, user_id: int, vehicle_id: int, now: datetime
) -> bool:
    return (
        await active_relationship(session, user_id, vehicle_id)
        or await current_history_grant(session, user_id, vehicle_id, now) is not None
    )


async def active_subscription_period(session: AsyncSession, user_id: int, now: datetime):
    return await session.scalar(
        select(SubscriptionPeriod)
        .where(
            SubscriptionPeriod.buyer_id == user_id,
            SubscriptionPeriod.revoked_at.is_(None),
            SubscriptionPeriod.starts_at <= now,
            SubscriptionPeriod.expires_at > now,
        )
        .order_by(SubscriptionPeriod.expires_at.desc())
        .limit(1)
    )


async def uncancelled_subscription_order(session: AsyncSession, user_id: int):
    return await session.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.buyer_id == user_id,
            PaymentOrder.provider == "stripe",
            PaymentOrder.product == "garage_monthly",
            PaymentOrder.provider_subscription_id.is_not(None),
            ~exists(
                select(SubscriptionCancellation.order_id).where(
                    SubscriptionCancellation.order_id == PaymentOrder.id,
                    SubscriptionCancellation.status == "confirmed",
                )
            ),
        )
        .order_by(PaymentOrder.created_at.desc())
        .limit(1)
    )
