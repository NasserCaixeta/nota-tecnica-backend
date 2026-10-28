from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
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
    session: AsyncSession,
    order: PaymentOrder,
    receipt: VerifiedPayment,
    payment: ProviderPayment,
    event_id: int,
):
    if order.product == "history_access":
        benefit = await session.scalar(
            select(HistoryAccessGrant).where(HistoryAccessGrant.order_id == order.id)
        )
        if benefit is not None:
            return
        benefit = HistoryAccessGrant(
            order_id=order.id,
            payment_id=receipt.id,
            buyer_id=order.buyer_id,
            vehicle_id=order.vehicle_id,
            starts_at=utc(payment.confirmed_at),
            expires_at=utc(payment.confirmed_at) + timedelta(hours=720),
        )
        target_type = "history_access_grant"
    else:
        benefit = await session.scalar(
            select(SubscriptionPeriod).where(SubscriptionPeriod.payment_id == receipt.id)
        )
        if benefit is not None:
            return
        benefit = SubscriptionPeriod(
            order_id=order.id,
            payment_id=receipt.id,
            buyer_id=order.buyer_id,
            provider_subscription_id=payment.subscription_id,
            starts_at=utc(payment.period_starts_at),
            expires_at=utc(payment.period_ends_at),
        )
        target_type = "subscription_period"
    session.add(benefit)
    await session.flush()
    await append_audit(
        session,
        actor_id=None,
        action="payments.benefit.granted",
        target_type=target_type,
        target_id=benefit.id,
        version=1,
        reason="verified_financial_confirmation",
        metadata={
            "order_id": order.id,
            "payment_id": receipt.id,
            "payment_event_id": event_id,
            "product": order.product,
            "environment": "sandbox",
        },
    )


async def revoke_benefit(
    session: AsyncSession, receipt: VerifiedPayment, now: datetime, event_id: int
):
    for model, target_type in (
        (HistoryAccessGrant, "history_access_grant"),
        (SubscriptionPeriod, "subscription_period"),
    ):
        benefit = await session.scalar(select(model).where(model.payment_id == receipt.id))
        if benefit is not None and benefit.revoked_at is None:
            benefit.revoked_at = now
            await append_audit(
                session,
                actor_id=None,
                action="payments.benefit.revoked",
                target_type=target_type,
                target_id=benefit.id,
                version=2,
                reason="canonical_financial_reversal",
                metadata={
                    "order_id": receipt.order_id,
                    "payment_id": receipt.id,
                    "payment_event_id": event_id,
                    "environment": "sandbox",
                },
            )
