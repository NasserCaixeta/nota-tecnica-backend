from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.garage.policy import get_garage_capacity
from app.modules.payments.access import active_subscription_period, uncancelled_subscription_order
from app.modules.payments.models import (
    HistoryAccessGrant,
    PaymentOrder,
    PaymentProduct,
    SubscriptionCancellation,
    SubscriptionPeriod,
)
from app.modules.payments.schemas import (
    PaymentOrderRead,
    SubscriptionPeriodRead,
    SubscriptionRead,
    SubscriptionSummaryRead,
)
from app.modules.payments.service import checkout_config
from app.modules.vehicles.models import Vehicle


def payment_config_read():
    settings = get_settings()
    ready = bool(settings.payments_enabled and settings.stripe_secret_key.get_secret_value())
    if ready:
        for product in PaymentProduct:
            try:
                checkout_config(product)
            except HTTPException:
                ready = False
    return {
        "enabled": ready,
        "environment": "sandbox",
        "label": "Ambiente de testes — sem cobrança real",
        "history_price_cents": settings.payments_history_price_cents,
        "subscription_price_cents": settings.payments_subscription_price_cents,
        "history_access_hours": 720,
        "garage_total_limit": 5,
    }


async def order_read(session: AsyncSession, order: PaymentOrder) -> PaymentOrderRead:
    result = PaymentOrderRead.model_validate(order)
    now = datetime.now(UTC)
    if order.vehicle_id is not None:
        result.plate = await session.scalar(
            select(Vehicle.plate).where(Vehicle.id == order.vehicle_id)
        )
    model = HistoryAccessGrant if order.product == "history_access" else SubscriptionPeriod
    grant = await session.scalar(
        select(model)
        .where(
            model.order_id == order.id,
            model.revoked_at.is_(None),
            model.starts_at <= now,
            model.expires_at > now,
        )
        .order_by(model.expires_at.desc())
        .limit(1)
    )
    if grant is not None:
        result.benefit_active = True
        result.benefit_expires_at = grant.expires_at
    return result


async def subscription_read(session: AsyncSession, user_id: int):
    now = datetime.now(UTC)
    capacity = await get_garage_capacity(session, user_id, now)
    period = await active_subscription_period(session, user_id, now)
    uncancelled = await uncancelled_subscription_order(session, user_id)
    order = uncancelled or await session.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.buyer_id == user_id,
            PaymentOrder.product == "garage_monthly",
            PaymentOrder.provider_subscription_id.is_not(None),
        )
        .order_by(PaymentOrder.created_at.desc())
        .limit(1)
    )
    cancellation = await session.get(SubscriptionCancellation, order.id) if order else None
    return SubscriptionSummaryRead(
        capacity_limit=capacity.limit,
        free_vehicle_id=capacity.free_vehicle_id,
        can_start_checkout=period is None and uncancelled is None,
        period=SubscriptionPeriodRead.model_validate(period) if period else None,
        subscription=SubscriptionRead(
            order_id=order.id, cancellation_status=cancellation.status if cancellation else None
        )
        if order
        else None,
    )
