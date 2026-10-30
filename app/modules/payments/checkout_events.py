from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
from app.modules.payments.models import CheckoutEvent, PaymentOrder, VerifiedPayment
from app.modules.payments.service import PENDING_STATES

CHECKOUT_TYPES = {"CHECKOUT_CREATED", "CHECKOUT_PAID", "CHECKOUT_EXPIRED", "CHECKOUT_CANCELED"}


async def pending_checkout_event_ids(session: AsyncSession):
    now = datetime.now(UTC)
    return list(
        (
            await session.scalars(
                select(CheckoutEvent.id)
                .where(
                    CheckoutEvent.provider == "stripe",
                    CheckoutEvent.status.in_(("pending", "reconciliation_required")),
                    or_(
                        CheckoutEvent.next_attempt_at.is_(None),
                        CheckoutEvent.next_attempt_at <= now,
                    ),
                )
                .order_by(CheckoutEvent.id)
                .limit(100)
            )
        ).all()
    )


async def process_checkout_event(session: AsyncSession, event_id: int):
    event = await session.scalar(
        select(CheckoutEvent)
        .where(CheckoutEvent.id == event_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if event is None or event.status == "processed":
        return
    if event.provider != "stripe":
        event.status = "ignored"
        event.last_error = "legacy_provider_disabled"
        await session.commit()
        return
    event.attempts += 1
    conditions = [PaymentOrder.provider_checkout_id == event.provider_checkout_id]
    if event.order_reference:
        conditions.append(PaymentOrder.id == event.order_reference)
    matches = list(
        (
            await session.scalars(
                select(PaymentOrder)
                .where(PaymentOrder.provider == "stripe", or_(*conditions))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    now = datetime.now(UTC)
    if (
        len(matches) != 1
        or (
            matches[0].provider_checkout_id
            and matches[0].provider_checkout_id != event.provider_checkout_id
        )
        or (event.order_reference and matches[0].id != event.order_reference)
    ):
        event.status = "reconciliation_required"
        event.last_error = "unknown_or_mismatched_checkout"
        event.next_attempt_at = now + timedelta(minutes=5)
        await session.commit()
        return
    order = matches[0]
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(730043, :buyer_id)"), {"buyer_id": order.buyer_id}
        )
    if order.provider_checkout_id is None:
        order.provider_checkout_id = event.provider_checkout_id
        # Recover identification, never invent a hosted URL or grant payment.
    previous = order.state
    if order.state in PENDING_STATES:
        paid_receipt = await session.scalar(
            select(VerifiedPayment.id)
            .where(
                VerifiedPayment.order_id == order.id,
                VerifiedPayment.state.in_(("CONFIRMED", "RECEIVED")),
            )
            .limit(1)
        )
        if paid_receipt is not None or event.event_type == "CHECKOUT_PAID":
            # Journey completion can recover identification, never prove benefit.
            order.state = "reconciliation_required"
        elif event.event_type == "CHECKOUT_EXPIRED":
            order.state = "expired"
        elif event.event_type == "CHECKOUT_CANCELED":
            order.state = "cancelled"
        elif event.event_type == "CHECKOUT_CREATED":
            order.state = "checkout_pending"
    if previous != order.state:
        await append_audit(
            session,
            actor_id=None,
            action="payments.checkout.state_changed",
            target_type="checkout_event",
            target_id=event.id,
            version=1,
            reason=event.event_type.lower(),
            metadata={
                "order_id": order.id,
                "previous_state": previous,
                "state": order.state,
                "environment": "sandbox",
            },
        )
    event.status = "processed"
    event.last_error = None
    event.next_attempt_at = None
    event.processed_at = now
    await session.commit()
