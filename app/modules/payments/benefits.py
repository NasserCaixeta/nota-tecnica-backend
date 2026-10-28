from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.gateway import ProviderPayment
from app.modules.payments.models import (
    HistoryAccessGrant,
    PaymentOrder,
    SubscriptionPeriod,
    VerifiedPayment,
)


def aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def utc(value: datetime) -> datetime:
    # SQLite test backend drops timezone metadata; persisted timestamps are UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def valid_confirmation(order: PaymentOrder, payment: ProviderPayment, now: datetime):
    return aware(payment.confirmed_at) and utc(order.created_at) <= payment.confirmed_at <= now


def valid_monthly_period(payment: ProviderPayment):
    start, end = payment.period_starts_at, payment.period_ends_at
    if not payment.subscription_id or not aware(start) or not aware(end):
        return False
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return (
        (end.year, end.month) == (year, month)
        and 28 <= (end.date() - start.date()).days <= 31
        and start.timetz().replace(tzinfo=None) == end.timetz().replace(tzinfo=None)
        and start <= payment.confirmed_at < end
    )


async def grant_benefit(
    session: AsyncSession, order: PaymentOrder, receipt: VerifiedPayment, payment: ProviderPayment
):
    if order.product == "history_access":
        grant = await session.scalar(
            select(HistoryAccessGrant).where(HistoryAccessGrant.order_id == order.id)
        )
        if grant is None:
            session.add(
                HistoryAccessGrant(
                    order_id=order.id,
                    payment_id=receipt.id,
                    buyer_id=order.buyer_id,
                    vehicle_id=order.vehicle_id,
                    starts_at=utc(payment.confirmed_at),
                    expires_at=utc(payment.confirmed_at) + timedelta(hours=720),
                )
            )
    else:
        period = await session.scalar(
            select(SubscriptionPeriod).where(SubscriptionPeriod.payment_id == receipt.id)
        )
        if period is None:
            session.add(
                SubscriptionPeriod(
                    order_id=order.id,
                    payment_id=receipt.id,
                    buyer_id=order.buyer_id,
                    provider_subscription_id=payment.subscription_id,
                    starts_at=utc(payment.period_starts_at),
                    expires_at=utc(payment.period_ends_at),
                )
            )
        order.provider_subscription_id = payment.subscription_id


async def revoke_benefit(session: AsyncSession, receipt: VerifiedPayment, now: datetime):
    for model in (HistoryAccessGrant, SubscriptionPeriod):
        benefit = await session.scalar(select(model).where(model.payment_id == receipt.id))
        if benefit is not None and benefit.revoked_at is None:
            benefit.revoked_at = now
