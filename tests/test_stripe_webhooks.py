import json
import time

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from tests.stripe_helpers import SECRET, event, signature, stripe_post


@pytest.fixture
def stripe_setup(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    from app.modules.payments import webhooks

    monkeypatch.setattr(webhooks, "dispatch_payment_event", lambda _: None)
    monkeypatch.setattr(webhooks, "dispatch_checkout_event", lambda _: None)


async def test_stripe_signature_replay_and_durable_inbox(client, db_session, stripe_setup):
    from app.modules.payments.models import PaymentEvent

    for _ in range(2):
        assert stripe_post(client, event()).status_code == 200
    rows = list(await db_session.scalars(select(PaymentEvent)))
    assert len(rows) == 1 and rows[0].provider == "stripe"
    assert rows[0].provider_payment_id == "pi_one" and rows[0].status == "pending"


@pytest.mark.parametrize("case", ["missing", "tampered", "expired", "future", "wrong-key", "live"])
async def test_invalid_or_live_stripe_events_never_enter_inbox(
    client, db_session, stripe_setup, case
):
    from app.modules.payments.models import PaymentEvent

    payload = event()
    if case == "live":
        payload["livemode"] = True
    body = json.dumps(payload).encode()
    signed = signature(
        body,
        "wrong" if case == "wrong-key" else SECRET,
        int(time.time()) + (-301 if case == "expired" else 301 if case == "future" else 0),
    )
    if case == "tampered":
        body = body.replace(b"pi_one", b"pi_two")
    response = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=body,
        headers={} if case == "missing" else {"Stripe-Signature": signed},
    )
    assert response.status_code in {400, 401, 422}
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0


async def test_checkout_complete_without_financial_object_only_records_journey(
    client, db_session, stripe_setup
):
    from app.modules.payments.models import CheckoutEvent, HistoryAccessGrant, PaymentEvent

    response = stripe_post(
        client,
        event(
            resource_id="cs_test_one",
            kind="checkout.session.completed",
            client_reference_id="opaque",
            mode="subscription",
            payment_status="paid",
        ),
    )
    assert response.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(CheckoutEvent)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
    assert await db_session.scalar(select(func.count()).select_from(HistoryAccessGrant)) == 0


async def test_broker_failure_does_not_lose_signed_invoice_event(
    client, db_session, stripe_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.models import PaymentEvent

    def fail(_):
        raise RuntimeError("broker-down")

    monkeypatch.setattr(webhooks, "dispatch_payment_event", fail)
    assert stripe_post(client, event(resource_id="in_one", kind="invoice.paid")).status_code == 200
    row = await db_session.scalar(select(PaymentEvent))
    assert row.provider_payment_id == "in_one" and row.status == "pending"


async def test_legacy_asaas_webhook_has_been_removed(client, stripe_setup):
    assert client.post("/api/v1/payments/webhooks/asaas", json={}).status_code == 404


async def test_checkout_timestamp_cannot_replace_missing_financial_confirmation(
    client, db_session, stripe_setup
):
    from dataclasses import replace
    from datetime import UTC, datetime

    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant, PaymentEvent
    from tests.test_payment_benefits import prepare_payment

    order, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(gateway.payment, confirmed_at=None)
    completed = event(
        event_id="evt_checkout",
        resource_id="cs_test_one",
        kind="checkout.session.completed",
        mode="payment",
        payment_status="paid",
        payment_intent=gateway.payment.id,
        client_reference_id=order.id,
    )
    assert stripe_post(client, completed).status_code == 200
    pending = await db_session.scalar(
        select(PaymentEvent).where(PaymentEvent.event_id == "evt_checkout")
    )
    await process_payment_event(db_session, pending.id, gateway, datetime.now(UTC))
    assert await db_session.scalar(select(HistoryAccessGrant)) is None
    financial = event(event_id="evt_financial", resource_id=gateway.payment.id)
    financial["created"] = int(datetime(2026, 10, 1, 12, tzinfo=UTC).timestamp())
    assert stripe_post(client, financial).status_code == 200
    confirmed = await db_session.scalar(
        select(PaymentEvent).where(PaymentEvent.event_id == "evt_financial")
    )
    await process_payment_event(db_session, confirmed.id, gateway, datetime.now(UTC))
    grant = await db_session.scalar(select(HistoryAccessGrant))
    assert grant.starts_at.replace(tzinfo=UTC) == datetime(2026, 10, 1, 12, tzinfo=UTC)
