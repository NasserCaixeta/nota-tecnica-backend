from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.benefits import (
    grant_benefit,
    revoke_benefit,
    utc,
    valid_confirmation,
    valid_monthly_period,
)
from app.modules.payments.gateway import GatewayUnavailable, GatewayUncertainOutcome, PaymentGateway
from app.modules.payments.models import PaymentEvent, PaymentOrder, VerifiedPayment
from app.modules.users.models import User

PAID = {"CONFIRMED", "RECEIVED"}
REVERSED = {
    "REFUNDED",
    "REFUND_REQUESTED",
    "REFUND_IN_PROGRESS",
    "PARTIALLY_REFUNDED",
    "CHARGEBACK_REQUESTED",
    "CHARGEBACK_DISPUTE",
    "AWAITING_CHARGEBACK_REVERSAL",
}


async def pending_payment_event_ids(
    session: AsyncSession, now: datetime | None = None
) -> list[int]:
    now = now or datetime.now(UTC)
    return list(
        (
            await session.scalars(
                select(PaymentEvent.id)
                .where(
                    PaymentEvent.status.in_(("pending", "reconciliation_required")),
                    or_(
                        PaymentEvent.next_attempt_at.is_(None), PaymentEvent.next_attempt_at <= now
                    ),
                )
                .order_by(PaymentEvent.id)
                .limit(100)
            )
        ).all()
    )


def defer(event: PaymentEvent, now: datetime, reason: str, *, reconciliation=False):
    event.status = "reconciliation_required" if reconciliation else "pending"
    event.last_error = reason
    event.next_attempt_at = now + timedelta(minutes=min(60, 2 ** min(event.attempts, 6)))


async def process_payment_event(
    session: AsyncSession, event_id: int, gateway: PaymentGateway, now: datetime
) -> None:
    event = await session.scalar(
        select(PaymentEvent)
        .where(PaymentEvent.id == event_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if event is None or event.status == "processed":
        return
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(730044, hashtext(:payment_id))"),
            {"payment_id": event.provider_payment_id},
        )
    event.attempts += 1
    try:
        payment = await gateway.fetch_payment(event.provider_payment_id)
    except (GatewayUnavailable, GatewayUncertainOutcome):
        defer(event, now, "provider_unavailable")
        await session.commit()
        return
    if payment.id != event.provider_payment_id:
        defer(event, now, "payment_identity_mismatch", reconciliation=True)
        await session.commit()
        return
    receipt = await session.scalar(
        select(VerifiedPayment).where(VerifiedPayment.provider_payment_id == payment.id)
    )
    conditions = []
    if receipt is not None:
        conditions.append(PaymentOrder.id == receipt.order_id)
    else:
        if payment.order_reference:
            conditions.append(PaymentOrder.id == payment.order_reference)
        if payment.checkout_id:
            conditions.append(PaymentOrder.provider_checkout_id == payment.checkout_id)
        if payment.subscription_id:
            conditions.append(PaymentOrder.provider_subscription_id == payment.subscription_id)
    matches = (
        list(
            (
                await session.scalars(
                    select(PaymentOrder)
                    .where(or_(*conditions))
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if conditions
        else []
    )
    if len(matches) != 1:
        defer(event, now, "unknown_or_ambiguous_order", reconciliation=True)
        await session.commit()
        return
    order = matches[0]
    # A previously verified financial ID is a durable binding. A later contact
    # change cannot prevent a canonical refund from revoking its own benefit.
    if receipt is not None and payment.state in REVERSED:
        receipt.state = payment.state
        receipt.checked_at = now
        await revoke_benefit(session, receipt, now)
        order.state = "refunded"
        event.status = "processed"
        event.last_error = None
        event.next_attempt_at = None
        event.processed_at = now
        await session.commit()
        return
    buyer = await session.get(User, order.buyer_id)
    matches_identity = (
        order.environment == "sandbox"
        and payment.amount_cents == order.amount_cents
        and payment.currency == order.currency
        and payment.customer_cpf == buyer.cpf
        and payment.customer_email is not None
        and payment.customer_email.casefold() == buyer.email.casefold()
        and (not payment.order_reference or payment.order_reference == order.id)
        and (
            not payment.checkout_id
            or not order.provider_checkout_id
            or payment.checkout_id == order.provider_checkout_id
        )
        and (
            not order.provider_subscription_id
            or payment.subscription_id == order.provider_subscription_id
        )
    )
    if not matches_identity:
        order.state = "reconciliation_required"
        defer(event, now, "payment_order_mismatch", reconciliation=True)
        await session.commit()
        return
    if receipt is None:
        receipt = VerifiedPayment(
            order_id=order.id, provider_payment_id=payment.id, state=payment.state, checked_at=now
        )
        session.add(receipt)
        await session.flush()
    elif receipt.order_id != order.id:
        defer(event, now, "payment_mapping_mismatch", reconciliation=True)
        await session.commit()
        return
    receipt.state = payment.state
    receipt.checked_at = now
    if payment.state in REVERSED:
        await revoke_benefit(session, receipt, now)
        order.state = "refunded"
    elif payment.state in PAID:
        if receipt.confirmed_at is not None:
            payment = replace(payment, confirmed_at=utc(receipt.confirmed_at))
        elif (
            payment.confirmed_at is None
            and event.provider_created_at is not None
            and (
                event.event_type == "PAYMENT_CONFIRMED"
                or (event.event_type == "PAYMENT_RECEIVED" and payment.billing_type == "PIX")
            )
        ):
            payment = replace(payment, confirmed_at=utc(event.provider_created_at))
        if not valid_confirmation(order, payment, now) or (
            order.product == "garage_monthly" and not valid_monthly_period(payment)
        ):
            order.state = "reconciliation_required"
            defer(event, now, "unverified_payment_time_or_period", reconciliation=True)
            await session.commit()
            return
        receipt.confirmed_at = payment.confirmed_at
        await grant_benefit(session, order, receipt, payment)
        order.state = "paid"
        if order.provider_checkout_id is None and payment.checkout_id:
            order.provider_checkout_id = payment.checkout_id
    elif payment.state in {"DELETED", "CANCELLED", "REPROVED_BY_RISK_ANALYSIS"}:
        await revoke_benefit(session, receipt, now)
        order.state = "cancelled" if payment.state in {"DELETED", "CANCELLED"} else "rejected"
    else:
        # Pending/overdue renewal neither creates a period nor revokes earlier paid ones.
        defer(event, now, "payment_not_confirmed")
        await session.commit()
        return
    event.status = "processed"
    event.last_error = None
    event.next_attempt_at = None
    event.processed_at = now
    await session.commit()
