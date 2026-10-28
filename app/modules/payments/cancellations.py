from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
from app.modules.payments.gateway import GatewayUnavailable, GatewayUncertainOutcome, PaymentGateway
from app.modules.payments.models import PaymentOrder, SubscriptionCancellation
from app.modules.payments.service import find_order
from app.modules.users.models import User


async def reconcile_cancellation(session: AsyncSession, order_id: str, gateway: PaymentGateway):
    cancellation = await session.scalar(
        select(SubscriptionCancellation)
        .where(SubscriptionCancellation.order_id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if cancellation is None or cancellation.status == "confirmed":
        return cancellation
    order = await session.get(PaymentOrder, order_id)
    try:
        confirmed = await gateway.cancel_subscription(order.provider_subscription_id)
    except (GatewayUnavailable, GatewayUncertainOutcome):
        confirmed = False
    now = datetime.now(UTC)
    next_status = "confirmed" if confirmed else "reconciliation_required"
    if cancellation.status != next_status:
        cancellation.decision_version += 1
        await append_audit(
            session,
            actor_id=None,
            action="payments.cancellation." + next_status,
            target_type="user_subscription",
            target_id=order.buyer_id,
            version=cancellation.decision_version,
            reason="provider_cancellation_verified" if confirmed else "provider_outcome_uncertain",
            metadata={"order_id": order.id, "environment": "sandbox"},
        )
    cancellation.status = next_status
    cancellation.confirmed_at = now if confirmed else None
    cancellation.next_attempt_at = None if confirmed else now + timedelta(minutes=5)
    await session.commit()
    return cancellation


async def cancel_subscription(
    session: AsyncSession, buyer: User, order_id: str, gateway: PaymentGateway
):
    order = await find_order(session, order_id, buyer, buyer_only=True)
    if order.product != "garage_monthly" or not order.provider_subscription_id:
        raise HTTPException(409, "No verified subscription is linked to this order")
    # Serialize creation of the durable request without holding a network call in
    # that transaction. Subsequent reconciliation locks the cancellation itself.
    await session.refresh(order, with_for_update=True)
    cancellation = await session.get(SubscriptionCancellation, order.id)
    if cancellation is None:
        cancellation = SubscriptionCancellation(
            order_id=order.id, status="pending", decision_version=1
        )
        session.add(cancellation)
        await append_audit(
            session,
            actor_id=buyer.id,
            action="payments.cancellation.requested",
            target_type="user_subscription",
            target_id=buyer.id,
            version=1,
            reason="buyer_requested_no_renewal",
            metadata={"order_id": order.id, "environment": "sandbox"},
        )
    await session.commit()
    return await reconcile_cancellation(session, order.id, gateway)


async def pending_cancellation_ids(session: AsyncSession):
    now = datetime.now(UTC)
    return list(
        (
            await session.scalars(
                select(SubscriptionCancellation.order_id)
                .where(
                    SubscriptionCancellation.status != "confirmed",
                    or_(
                        SubscriptionCancellation.next_attempt_at.is_(None),
                        SubscriptionCancellation.next_attempt_at <= now,
                    ),
                )
                .limit(100)
            )
        ).all()
    )
