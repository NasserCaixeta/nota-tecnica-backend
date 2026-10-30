from datetime import UTC, datetime

from sqlalchemy import select

from app.modules.payments.checkout_events import process_checkout_event
from app.modules.payments.events import process_payment_event
from app.modules.payments.models import CheckoutEvent, HistoryAccessGrant
from tests.test_payment_benefits import add_event, prepare_payment


async def lifecycle_event(session, kind):
    event = CheckoutEvent(
        provider="stripe",
        environment="sandbox",
        event_id=kind,
        event_type=kind,
        provider_checkout_id="checkout_1",
        order_reference="opaque-payment-order",
    )
    session.add(event)
    await session.commit()
    await process_checkout_event(session, event.id)
    return event


async def test_out_of_order_checkout_events_do_not_reopen_or_grant_expired_order(
    client, db_session
):
    order, _ = await prepare_payment(client, db_session)
    await lifecycle_event(db_session, "CHECKOUT_EXPIRED")
    await lifecycle_event(db_session, "CHECKOUT_CREATED")
    await lifecycle_event(db_session, "CHECKOUT_PAID")
    assert order.state == "expired"
    assert await db_session.scalar(select(HistoryAccessGrant)) is None


async def test_checkout_expiration_cannot_demote_verified_financial_payment(client, db_session):
    order, gateway = await prepare_payment(client, db_session)
    financial = await add_event(db_session)
    await process_payment_event(
        db_session, financial.id, gateway, datetime(2026, 10, 27, tzinfo=UTC)
    )
    await lifecycle_event(db_session, "CHECKOUT_EXPIRED")
    assert order.state == "paid"
    assert (await db_session.scalar(select(HistoryAccessGrant))).revoked_at is None
