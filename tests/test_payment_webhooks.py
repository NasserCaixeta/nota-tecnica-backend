import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from tests.stripe_helpers import SECRET, event, stripe_post


@pytest.fixture
def webhook_setup(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()


async def test_webhook_authentication_and_replay_persist_once(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.models import PaymentEvent

    sent = []
    monkeypatch.setattr(webhooks, "dispatch_payment_event", lambda key: sent.append(key))
    assert stripe_post(client, event(), secret="wrong-secret").status_code == 401
    assert client.post("/api/v1/payments/webhooks/stripe", json=event()).status_code == 401
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
    for _ in range(2):
        assert stripe_post(client, event()).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    assert len(set(sent)) == 1


async def test_webhook_survives_dispatch_failure_and_recovers(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.events import pending_payment_event_ids
    from app.modules.payments.models import PaymentEvent

    def fail(_):
        raise RuntimeError("Queue unavailable")

    monkeypatch.setattr(webhooks, "dispatch_payment_event", fail)
    assert stripe_post(client, event()).status_code == 200
    row = await db_session.scalar(select(PaymentEvent))
    assert row.status == "pending"
    assert await pending_payment_event_ids(db_session) == [row.id]


async def test_checkout_event_cannot_grant_payment(client, db_session, webhook_setup, monkeypatch):
    from app.modules.payments import webhooks
    from app.modules.payments.models import CheckoutEvent, HistoryAccessGrant

    monkeypatch.setattr(webhooks, "dispatch_checkout_event", lambda _: None)
    assert (
        stripe_post(
            client, event(resource_id="cs_test_one", kind="checkout.session.completed")
        ).status_code
        == 200
    )
    assert (await db_session.scalar(select(CheckoutEvent))).event_type == "CHECKOUT_PAID"
    assert await db_session.scalar(select(HistoryAccessGrant)) is None


async def test_checkout_expiration_is_durable_and_allows_a_new_attempt(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.gateway import CheckoutSession
    from app.modules.payments.models import CheckoutEvent
    from app.modules.payments.router import get_payment_gateway
    from tests.test_checkout_orders import CheckoutGateway
    from tests.test_maintenance import auth_headers

    monkeypatch.setenv("PAYMENTS_SUBSCRIPTION_PRICE_CENTS", "4900")
    monkeypatch.setenv("PAYMENTS_CALLBACK_BASE_URL", "https://pilot.test")
    get_settings.cache_clear()
    monkeypatch.setattr(webhooks, "dispatch_checkout_event", lambda _: None)
    gateway = CheckoutGateway()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    headers = auth_headers(client)
    first = client.post("/api/v1/payments/subscription-checkouts", headers=headers, json={}).json()
    payload = event(
        resource_id="checkout-test-id",
        kind="checkout.session.expired",
        client_reference_id=first["id"],
    )
    for _ in range(2):
        assert stripe_post(client, payload).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(CheckoutEvent)) == 1
    from app.modules.payments.checkout_events import process_checkout_event

    row = await db_session.scalar(select(CheckoutEvent))
    await process_checkout_event(db_session, row.id)
    assert (
        client.get("/api/v1/payments/orders/" + first["id"], headers=headers).json()["state"]
        == "expired"
    )

    async def create_new(snapshot):
        gateway.created.append(snapshot.id)
        return CheckoutSession("checkout-new", "https://checkout.stripe.com/c/pay/cs_test_new")

    gateway.create_checkout = create_new
    second = client.post("/api/v1/payments/subscription-checkouts", headers=headers, json={})
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    assert len(gateway.created) == 2
