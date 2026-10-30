import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.modules.payments.events import process_payment_event
from app.modules.payments.gateway import ProviderPayment
from app.modules.payments.models import (
    HistoryAccessGrant,
    PaymentEvent,
    PaymentOrder,
    SubscriptionPeriod,
    VerifiedPayment,
)
from app.modules.vehicles.models import Vehicle
from tests.integration.test_admin_concurrency import prepare_users
from tests.test_payment_benefits import FinancialGateway


@pytest.mark.parametrize("aliased", [False, True])
async def test_simultaneous_payment_confirmations_create_one_benefit(pg_engine, aliased):
    factory = await prepare_users(pg_engine)
    async with factory() as session:
        vehicle = Vehicle(plate="ABC1D23")
        session.add(vehicle)
        await session.flush()
        session.add(
            PaymentOrder(
                id="order",
                buyer_id=3,
                product="history_access",
                vehicle_id=vehicle.id,
                amount_cents=1900,
                currency="BRL",
                environment="sandbox",
                state="checkout_pending",
                callback_url="https://pilot.test",
                created_at=datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
        events = [
            PaymentEvent(
                provider="stripe",
                environment="sandbox",
                event_id=f"evt_{i}",
                event_type="PAYMENT_CONFIRMED",
                provider_payment_id="pay_alias" if aliased and i else "pay_1",
            )
            for i in range(2)
        ]
        session.add_all(events)
        await session.commit()
        event_ids = [event.id for event in events]

    class CanonicalGateway(FinancialGateway):
        async def fetch_payment(self, payment_id):
            payment = await super().fetch_payment(payment_id)
            return replace(payment, source_id=payment_id)

    gateway = CanonicalGateway(
        ProviderPayment(
            id="pay_1",
            state="CONFIRMED",
            order_reference="order",
            amount_cents=1900,
            currency="BRL",
            customer_id="cus_1",
            customer_user_reference="3",
            customer_email="driver@example.com",
            confirmed_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        )
    )

    async def confirm(event_id):
        async with factory() as session:
            await process_payment_event(
                session, event_id, gateway, datetime(2026, 10, 27, tzinfo=UTC)
            )

    await asyncio.gather(*(confirm(event_id) for event_id in event_ids))
    # A restarted worker may revisit the same durable IDs safely.
    await asyncio.gather(*(confirm(event_id) for event_id in event_ids))
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(HistoryAccessGrant)) == 1
        assert await session.scalar(select(func.count()).select_from(VerifiedPayment)) == 1
        assert list(await session.scalars(select(PaymentEvent.status))) == [
            "processed",
            "processed",
        ]


async def test_checkout_racing_confirmation_cannot_create_second_subscription(
    pg_engine, monkeypatch
):
    from fastapi import HTTPException

    from app.core.config import get_settings
    from app.modules.payments.gateway import CheckoutSession
    from app.modules.payments.models import PaymentProduct
    from app.modules.payments.service import create_order
    from app.modules.users.models import User

    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv(
        "STRIPE_WEBHOOK_SECRET", "whsec_separate-webhook-secret-at-least-32-characters"
    )
    monkeypatch.setenv("PAYMENTS_SUBSCRIPTION_PRICE_CENTS", "4900")
    monkeypatch.setenv("PAYMENTS_CALLBACK_BASE_URL", "https://pilot.test")
    get_settings.cache_clear()

    factory = await prepare_users(pg_engine)
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    async with factory() as session:
        session.add(
            PaymentOrder(
                id="order",
                buyer_id=3,
                product="garage_monthly",
                amount_cents=4900,
                currency="BRL",
                environment="sandbox",
                state="checkout_pending",
                callback_url="https://pilot.test",
                created_at=start,
            )
        )
        event = PaymentEvent(
            provider="stripe",
            environment="sandbox",
            event_id="evt_1",
            event_type="PAYMENT_CONFIRMED",
            provider_payment_id="pay_1",
        )
        session.add(event)
        await session.commit()
        event_id = event.id

    class Gateway(FinancialGateway):
        creations = []

        async def create_checkout(self, order):
            self.creations.append(order.id)
            return CheckoutSession("unexpected", "https://checkout.stripe.com/c/pay/cs_test_unused")

    gateway = Gateway(
        ProviderPayment(
            id="pay_1",
            state="CONFIRMED",
            order_reference="order",
            amount_cents=4900,
            currency="BRL",
            customer_id="cus_1",
            customer_user_reference="3",
            customer_email="driver@example.com",
            confirmed_at=start,
            subscription_id="sub_1",
            period_starts_at=start,
            period_ends_at=end,
        )
    )

    async def checkout():
        async with factory() as session:
            user = await session.get(User, 3)
            try:
                order = await create_order(session, user, PaymentProduct.GARAGE_MONTHLY, gateway)
                assert order.id == "order"
            except HTTPException as exc:
                assert exc.status_code == 409

    async def confirm():
        async with factory() as session:
            await process_payment_event(session, event_id, gateway, now)

    await asyncio.gather(confirm(), checkout())
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentOrder)) == 1
    assert gateway.creations == []
    get_settings.cache_clear()


@pytest.mark.parametrize("product", ["history_access", "garage_monthly"])
async def test_stale_confirmation_after_aliased_refund_cannot_create_first_benefit(
    pg_engine, product
):
    factory = await prepare_users(pg_engine)
    now = datetime(2026, 10, 27, tzinfo=UTC)
    async with factory() as session:
        vehicle = Vehicle(plate="ABC1D23")
        session.add(vehicle)
        await session.flush()
        session.add(
            PaymentOrder(
                id="refund-race",
                buyer_id=3,
                product=product,
                vehicle_id=vehicle.id if product == "history_access" else None,
                amount_cents=1900,
                currency="BRL",
                environment="sandbox",
                state="checkout_pending",
                callback_url="https://pilot.test",
                created_at=datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
        canonical = "in_race" if product == "garage_monthly" else "pi_race"
        events = [
            PaymentEvent(
                provider="stripe",
                environment="sandbox",
                event_id=f"evt_race_{i}",
                event_type="PAYMENT_CONFIRMED" if i == 0 else "PAYMENT_REFUNDED",
                provider_payment_id=canonical if i == 0 else "ch_race",
            )
            for i in range(2)
        ]
        session.add_all(events)
        await session.commit()
        ids = [event.id for event in events]

    snapshot = ProviderPayment(
        id=canonical,
        state="CONFIRMED",
        order_reference="refund-race",
        amount_cents=1900,
        currency="BRL",
        customer_id="cus_race",
        customer_user_reference="3",
        customer_email="driver@example.com",
        confirmed_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        subscription_id="sub_race" if product == "garage_monthly" else None,
        period_starts_at=datetime(2026, 10, 1, tzinfo=UTC),
        period_ends_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    confirmation_read = asyncio.Event()
    refund_processed = asyncio.Event()

    class RacingGateway:
        async def fetch_payment(self, identity):
            if identity == canonical:
                confirmation_read.set()
                await asyncio.wait_for(refund_processed.wait(), timeout=10)
                return snapshot
            return replace(snapshot, source_id="ch_race", state="REFUNDED")

    async def confirm():
        async with factory() as session:
            await process_payment_event(session, ids[0], RacingGateway(), now)

    async def refund():
        await asyncio.wait_for(confirmation_read.wait(), timeout=10)
        async with factory() as session:
            await process_payment_event(session, ids[1], RacingGateway(), now)
        refund_processed.set()

    await asyncio.gather(confirm(), refund())
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(HistoryAccessGrant)) == 0
        assert await session.scalar(select(func.count()).select_from(SubscriptionPeriod)) == 0
        assert (await session.get(PaymentOrder, "refund-race")).state == "refunded"
        assert (await session.scalar(select(VerifiedPayment))).state == "REFUNDED"
        assert list(await session.scalars(select(PaymentEvent.status))) == [
            "processed",
            "processed",
        ]
