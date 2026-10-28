from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.payments.gateway import (
    CheckoutOrder,
    GatewayUnavailable,
    GatewayUncertainOutcome,
    PaymentGateway,
)
from app.modules.payments.models import PaymentOrder, PaymentProduct
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

PENDING_STATES = ("created", "checkout_pending", "reconciliation_required", "checkout_failed")


def checkout_config(product: PaymentProduct):
    settings = get_settings()
    price = (
        settings.payments_history_price_cents
        if product == PaymentProduct.HISTORY_ACCESS
        else settings.payments_subscription_price_cents
    )
    base_url = settings.payments_callback_base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if (
        not settings.payments_enabled
        or price is None
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            503, "Sandbox payments require explicit prices and an HTTPS callback URL"
        )
    return price, base_url


def checkout_snapshot(order: PaymentOrder) -> CheckoutOrder:
    return CheckoutOrder(
        order.id,
        order.product,
        order.amount_cents,
        order.currency,
        order.callback_url,
        order.created_at,
    )


async def find_order(session: AsyncSession, order_id: str, actor: User, *, buyer_only=False):
    order = await session.get(PaymentOrder, order_id, populate_existing=True)
    if order is None or (order.buyer_id != actor.id and (buyer_only or not actor.is_admin)):
        raise HTTPException(404, "Payment order not found")
    return order


async def update_checkout(
    session: AsyncSession, order: PaymentOrder, gateway: PaymentGateway, *, create=False
):
    try:
        result = (
            await gateway.create_checkout(checkout_snapshot(order))
            if create
            else await gateway.reconcile_checkout(checkout_snapshot(order))
        )
        order.state = "checkout_pending" if result else "reconciliation_required"
        if result:
            order.provider_checkout_id = result.provider_id
            order.checkout_url = result.url
    except GatewayUncertainOutcome:
        order.state = "reconciliation_required"
    except GatewayUnavailable:
        order.state = "checkout_failed" if create else "reconciliation_required"
    await session.commit()
    await session.refresh(order)
    return order


async def create_order(
    session: AsyncSession,
    buyer: User,
    product: PaymentProduct,
    gateway: PaymentGateway,
    plate: str | None = None,
):
    price, base_url = checkout_config(product)
    vehicle_id = None
    if product == PaymentProduct.HISTORY_ACCESS:
        vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == plate))
        if (
            vehicle is None
            or await session.scalar(
                published_maintenance_select()
                .where(MaintenanceRecord.vehicle_id == vehicle.id)
                .limit(1)
            )
            is None
        ):
            raise HTTPException(409, "No published history is available for this plate")
        vehicle_id = vehicle.id
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(730043, :buyer_id)"), {"buyer_id": buyer.id}
        )
    existing = await session.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.buyer_id == buyer.id,
            PaymentOrder.product == product,
            PaymentOrder.vehicle_id == vehicle_id,
            PaymentOrder.state.in_(PENDING_STATES),
        )
        .order_by(PaymentOrder.created_at.desc())
        .limit(1)
    )
    if existing:
        return existing
    order_id = str(uuid4())
    order = PaymentOrder(
        id=order_id,
        buyer_id=buyer.id,
        product=product,
        vehicle_id=vehicle_id,
        amount_cents=price,
        currency="BRL",
        environment="sandbox",
        state="created",
        callback_url=f"{base_url}/app/compras/{order_id}",
        created_at=datetime.now(UTC),
    )
    session.add(order)
    # Persist the reference before the network request, including process termination.
    await session.commit()
    return await update_checkout(session, order, gateway, create=True)


async def retry_order(session: AsyncSession, buyer: User, order_id: str, gateway: PaymentGateway):
    order = await find_order(session, order_id, buyer, buyer_only=True)
    if order.state == "checkout_pending":
        return order
    if order.state not in PENDING_STATES:
        raise HTTPException(409, "This order cannot be retried")
    return await update_checkout(session, order, gateway)
