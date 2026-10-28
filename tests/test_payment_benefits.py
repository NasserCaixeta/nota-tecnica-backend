from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from tests.test_maintenance import auth_headers


class FinancialGateway:
    def __init__(self, payment):
        self.payment = payment
        self.calls = []

    async def fetch_payment(self, payment_id):
        self.calls.append(payment_id)
        return self.payment


async def prepare_payment(client, session, *, product="history_access"):
    from app.modules.payments.gateway import ProviderPayment
    from app.modules.payments.models import PaymentOrder
    from app.modules.users.models import User
    from tests.test_vehicles import vehicle_payload

    h = auth_headers(client)
    vehicle = client.post("/api/v1/garage/vehicles", headers=h, json=vehicle_payload())
    assert vehicle.status_code == 201, vehicle.text
    buyer = await session.scalar(select(User).where(User.email == "driver@example.com"))
    order = PaymentOrder(
        id="opaque-payment-order",
        buyer_id=buyer.id,
        product=product,
        vehicle_id=vehicle.json()["vehicle_id"] if product == "history_access" else None,
        amount_cents=1900,
        currency="BRL",
        environment="sandbox",
        state="checkout_pending",
        provider_checkout_id="checkout_1",
        callback_url="https://pilot.test",
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    session.add(order)
    await session.commit()
    payment = ProviderPayment(
        id="pay_1",
        state="CONFIRMED",
        order_reference=order.id,
        amount_cents=1900,
        currency="BRL",
        customer_id="cus_1",
        customer_cpf=buyer.cpf,
        customer_email=buyer.email,
        confirmed_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        checkout_id="checkout_1",
    )
    return order, FinancialGateway(payment)


async def add_event(session, *, event_id="evt_1", payment_id="pay_1", kind="PAYMENT_CONFIRMED"):
    from app.modules.payments.models import PaymentEvent

    event = PaymentEvent(
        provider="asaas",
        environment="sandbox",
        event_id=event_id,
        event_type=kind,
        provider_payment_id=payment_id,
        status="pending",
    )
    session.add(event)
    await session.commit()
    return event


async def test_duplicate_confirmations_grant_exact_720_hours_from_verified_time(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    order, gateway = await prepare_payment(client, db_session)
    for event_id in ("evt_1", "evt_2"):
        event = await add_event(db_session, event_id=event_id)
        await process_payment_event(
            db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC)
        )
    assert await db_session.scalar(select(func.count()).select_from(HistoryAccessGrant)) == 1
    grant = await db_session.scalar(select(HistoryAccessGrant))
    assert grant.starts_at.replace(tzinfo=UTC) == gateway.payment.confirmed_at
    assert grant.expires_at - grant.starts_at == timedelta(hours=720)
    assert order.state == "paid"


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": 1},
        {"currency": "USD"},
        {"customer_cpf": "00000000000"},
        {"customer_email": "other@example.com"},
        {"confirmed_at": None},
        {"confirmed_at": datetime(2026, 10, 1, 12)},
        {"checkout_id": "other-checkout"},
    ],
)
async def test_mismatched_or_imprecise_payment_has_no_benefit(client, db_session, changes):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    order, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(gateway.payment, **changes)
    event = await add_event(db_session)
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert await db_session.scalar(select(func.count()).select_from(HistoryAccessGrant)) == 0
    assert order.state == "reconciliation_required"
    assert event.status == "reconciliation_required"


@pytest.mark.parametrize("refund_first", [False, True])
async def test_out_of_order_events_converge_to_canonical_refund(client, db_session, refund_first):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    order, gateway = await prepare_payment(client, db_session)
    if not refund_first:
        confirmation = await add_event(db_session)
        await process_payment_event(db_session, confirmation.id, gateway, datetime.now(UTC))
    gateway.payment = replace(gateway.payment, state="REFUNDED")
    for i, kind in enumerate(("PAYMENT_REFUNDED", "PAYMENT_CONFIRMED")):
        event = await add_event(db_session, event_id=f"evt-refund-{i}", kind=kind)
        await process_payment_event(db_session, event.id, gateway, datetime.now(UTC))
    grant = await db_session.scalar(select(HistoryAccessGrant))
    assert grant is None or grant.revoked_at is not None
    assert order.state == "refunded"


async def test_monthly_period_uses_verified_boundaries_and_not_thirty_days(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import SubscriptionPeriod

    order, gateway = await prepare_payment(client, db_session, product="garage_monthly")
    gateway.payment = replace(
        gateway.payment,
        subscription_id="sub_1",
        period_starts_at=datetime(2026, 10, 1, tzinfo=UTC),
        period_ends_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    for event_id in ("evt_1", "evt_2"):
        event = await add_event(db_session, event_id=event_id)
        await process_payment_event(db_session, event.id, gateway, datetime.now(UTC))
    assert await db_session.scalar(select(func.count()).select_from(SubscriptionPeriod)) == 1
    period = await db_session.scalar(select(SubscriptionPeriod))
    assert period.expires_at - period.starts_at == timedelta(days=31)
    assert order.provider_subscription_id == "sub_1"


async def test_authenticated_confirmation_event_time_used_only_for_matching_financial_state(
    client, db_session
):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    order, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(gateway.payment, confirmed_at=None, billing_type="CREDIT_CARD")
    event = await add_event(db_session)
    event.provider_created_at = datetime(2026, 10, 1, 12, tzinfo=UTC)
    await db_session.commit()
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    grant = await db_session.scalar(select(HistoryAccessGrant))
    assert grant is not None
    assert grant.starts_at.replace(tzinfo=UTC) == event.provider_created_at.replace(tzinfo=UTC)


async def test_later_card_received_event_does_not_invent_confirmation_time(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    _, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(
        gateway.payment, state="RECEIVED", confirmed_at=None, billing_type="CREDIT_CARD"
    )
    event = await add_event(db_session, kind="PAYMENT_RECEIVED")
    event.provider_created_at = datetime(2026, 10, 20, 12, tzinfo=UTC)
    await db_session.commit()
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert await db_session.scalar(select(HistoryAccessGrant)) is None


async def test_refund_revokes_only_the_corresponding_payment(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    _, gateway = await prepare_payment(client, db_session)
    event = await add_event(db_session)
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    gateway.payment = replace(gateway.payment, id="pay_2", state="REFUNDED")
    refund = await add_event(
        db_session, event_id="evt_refund", payment_id="pay_2", kind="PAYMENT_REFUNDED"
    )
    await process_payment_event(db_session, refund.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert (await db_session.scalar(select(HistoryAccessGrant))).revoked_at is None


async def test_processing_failure_rolls_back_receipt_benefit_and_event(
    client, db_session, monkeypatch
):
    from app.modules.payments import events
    from app.modules.payments.models import (
        HistoryAccessGrant,
        PaymentEvent,
        PaymentOrder,
        VerifiedPayment,
    )

    order, gateway = await prepare_payment(client, db_session)
    event = await add_event(db_session)
    event_id, order_id = event.id, order.id

    async def crash(*args):
        raise RuntimeError("Simulated crash")

    monkeypatch.setattr(events, "grant_benefit", crash)
    with pytest.raises(RuntimeError, match="Simulated crash"):
        await events.process_payment_event(
            db_session, event_id, gateway, datetime(2026, 10, 27, tzinfo=UTC)
        )
    await db_session.rollback()
    assert await db_session.scalar(select(VerifiedPayment)) is None
    assert await db_session.scalar(select(HistoryAccessGrant)) is None
    assert (await db_session.get(PaymentEvent, event_id)).status == "pending"
    assert (await db_session.get(PaymentOrder, order_id)).state == "checkout_pending"


async def test_known_payment_refund_revokes_even_if_payer_contact_later_changes(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    _, gateway = await prepare_payment(client, db_session)
    event = await add_event(db_session)
    now = datetime(2026, 10, 27, tzinfo=UTC)
    await process_payment_event(db_session, event.id, gateway, now)
    gateway.payment = replace(
        gateway.payment, state="REFUNDED", customer_email="changed@example.com"
    )
    refund = await add_event(db_session, event_id="evt_refund", kind="PAYMENT_REFUNDED")
    await process_payment_event(db_session, refund.id, gateway, now)
    assert (await db_session.scalar(select(HistoryAccessGrant))).revoked_at is not None


async def test_history_720_hours_uses_utc_across_daylight_saving_change(client, db_session):
    from zoneinfo import ZoneInfo

    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    _, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(
        gateway.payment,
        confirmed_at=datetime(2026, 10, 15, 12, tzinfo=ZoneInfo("America/New_York")),
    )
    event = await add_event(db_session)
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 11, 20, tzinfo=UTC))
    grant = await db_session.scalar(select(HistoryAccessGrant))
    assert grant.starts_at.replace(tzinfo=UTC) == datetime(2026, 10, 15, 16, tzinfo=UTC)
    assert grant.expires_at.replace(tzinfo=UTC) == datetime(2026, 11, 14, 16, tzinfo=UTC)


async def test_later_receipt_cannot_require_a_new_boundary_for_already_confirmed_period(
    client, db_session
):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import SubscriptionPeriod

    order, gateway = await prepare_payment(client, db_session, product="garage_monthly")
    gateway.payment = replace(
        gateway.payment,
        subscription_id="sub_1",
        period_starts_at=datetime(2026, 10, 1, tzinfo=UTC),
        period_ends_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    first = await add_event(db_session)
    await process_payment_event(db_session, first.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    gateway.payment = replace(
        gateway.payment, state="RECEIVED", period_starts_at=None, period_ends_at=None
    )
    second = await add_event(db_session, event_id="evt_received", kind="PAYMENT_RECEIVED")
    await process_payment_event(db_session, second.id, gateway, datetime(2026, 11, 20, tzinfo=UTC))
    assert second.status == "processed"
    assert order.state == "paid"
    assert await db_session.scalar(select(func.count()).select_from(SubscriptionPeriod)) == 1


async def test_subscription_can_be_cancelled_while_time_is_awaiting_reconciliation(
    client, db_session
):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.readers import subscription_read

    order, gateway = await prepare_payment(client, db_session, product="garage_monthly")
    gateway.payment = replace(gateway.payment, subscription_id="sub_1", confirmed_at=None)
    event = await add_event(db_session)
    await process_payment_event(db_session, event.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert order.provider_subscription_id == "sub_1"
    summary = await subscription_read(db_session, order.buyer_id)
    assert summary.subscription.order_id == order.id
    assert summary.can_start_checkout is False
    assert summary.period is None
    from app.modules.payments.router import get_payment_gateway
    from tests.test_auth_users import login

    async def cancel_remote(subscription_id):
        assert subscription_id == "sub_1"
        return True

    gateway.cancel_subscription = cancel_remote
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    headers = {"Authorization": f"Bearer {login(client, email='driver@example.com')}"}
    response = client.post(f"/api/v1/payments/subscriptions/{order.id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


async def test_payment_decisions_are_audited_once_in_the_same_transaction(client, db_session):
    from app.modules.audit.models import AuditEvent
    from app.modules.payments.events import process_payment_event

    order, gateway = await prepare_payment(client, db_session)
    event = await add_event(db_session)
    now = datetime(2026, 10, 27, tzinfo=UTC)
    await process_payment_event(db_session, event.id, gateway, now)
    duplicate = await add_event(db_session, event_id="evt_2")
    await process_payment_event(db_session, duplicate.id, gateway, now)
    granted = list(
        await db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "payments.benefit.granted")
        )
    )
    assert len(granted) == 1
    assert granted[0].actor_id is None
    assert granted[0].version == 1
    assert granted[0].event_metadata["payment_event_id"] == event.id
    assert granted[0].event_metadata["order_id"] == order.id
    gateway.payment = replace(gateway.payment, state="REFUNDED")
    refund = await add_event(db_session, event_id="evt_refund", kind="PAYMENT_REFUNDED")
    await process_payment_event(db_session, refund.id, gateway, now)
    revoked = list(
        await db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "payments.benefit.revoked")
        )
    )
    assert len(revoked) == 1
    assert revoked[0].version == 2
    assert revoked[0].event_metadata["payment_event_id"] == refund.id


async def test_failed_financial_audit_rolls_back_benefit_and_event(client, db_session, monkeypatch):
    from app.modules.audit.models import AuditEvent
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant, PaymentEvent, VerifiedPayment

    _, gateway = await prepare_payment(client, db_session)
    event = await add_event(db_session)
    event_id = event.id

    async def unavailable(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.payments.benefits.append_audit", unavailable)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await process_payment_event(
            db_session, event_id, gateway, datetime(2026, 10, 27, tzinfo=UTC)
        )
    await db_session.rollback()
    assert await db_session.scalar(select(HistoryAccessGrant)) is None
    assert await db_session.scalar(select(VerifiedPayment)) is None
    assert (
        await db_session.scalar(select(AuditEvent).where(AuditEvent.action.like("payments.%")))
        is None
    )
    assert (await db_session.get(PaymentEvent, event_id)).status == "pending"
