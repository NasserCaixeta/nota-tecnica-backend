import pytest
from sqlalchemy import func, select

from app.core.config import get_settings


@pytest.fixture
def webhook_setup(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("ASAAS_WEBHOOK_TOKEN", "separate-webhook-secret-32-characters")
    monkeypatch.setenv("ASAAS_API_KEY", "different-api-secret")
    get_settings.cache_clear()
    return {"asaas-access-token": "separate-webhook-secret-32-characters"}


def event_body(event_id="evt_1", payment_id="pay_1"):
    return {
        "id": event_id,
        "event": "PAYMENT_CONFIRMED",
        "dateCreated": "2026-10-27 12:01:01",
        "payment": {"id": payment_id},
    }


async def test_webhook_authentication_and_replay_persist_once(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.models import PaymentEvent

    sent = []
    monkeypatch.setattr(webhooks, "dispatch_payment_event", lambda event_id: sent.append(event_id))
    for headers in (
        {},
        {"asaas-access-token": "wrong"},
        {"asaas-access-token": "different-api-secret"},
    ):
        assert (
            client.post(
                "/api/v1/payments/webhooks/asaas", headers=headers, json=event_body()
            ).status_code
            == 401
        )
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/payments/webhooks/asaas", headers=webhook_setup, json=event_body()
            ).status_code
            == 200
        )
    assert await db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    assert len(set(sent)) == 1


async def test_webhook_survives_dispatch_failure_and_recovers(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
    from app.modules.payments.events import pending_payment_event_ids
    from app.modules.payments.models import PaymentEvent

    def unavailable(event_id):
        raise RuntimeError("Queue unavailable")

    monkeypatch.setattr(webhooks, "dispatch_payment_event", unavailable)
    response = client.post(
        "/api/v1/payments/webhooks/asaas", headers=webhook_setup, json=event_body()
    )
    assert response.status_code == 200
    row = await db_session.scalar(select(PaymentEvent))
    assert row.status == "pending"
    assert await pending_payment_event_ids(db_session) == [row.id]


async def test_checkout_event_cannot_grant_payment(client, db_session, webhook_setup, monkeypatch):
    from app.modules.payments import webhooks
    from app.modules.payments.models import CheckoutEvent, HistoryAccessGrant

    monkeypatch.setattr(webhooks, "dispatch_checkout_event", lambda _: None)
    response = client.post(
        "/api/v1/payments/webhooks/asaas",
        headers=webhook_setup,
        json={"id": "checkout_event", "event": "CHECKOUT_PAID", "checkout": {"id": "checkout_1"}},
    )
    assert response.status_code == 200
    assert (await db_session.scalar(select(CheckoutEvent))).event_type == "CHECKOUT_PAID"
    assert await db_session.scalar(select(HistoryAccessGrant)) is None


async def test_checkout_expiration_is_durable_and_allows_a_new_attempt(
    client, db_session, webhook_setup, monkeypatch
):
    from app.modules.payments import webhooks
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
    h = auth_headers(client)
    first = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={}).json()
    payload = {
        "id": "evt_expired",
        "event": "CHECKOUT_EXPIRED",
        "checkout": {"id": "checkout-test-id", "externalReference": first["id"]},
    }
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/payments/webhooks/asaas", headers=webhook_setup, json=payload
            ).status_code
            == 200
        )
    assert await db_session.scalar(select(func.count()).select_from(CheckoutEvent)) == 1
    from app.modules.payments.checkout_events import process_checkout_event

    event = await db_session.scalar(select(CheckoutEvent))
    await process_checkout_event(db_session, event.id)
    assert (
        client.get(f"/api/v1/payments/orders/{first['id']}", headers=h).json()["state"] == "expired"
    )
    # The new creation gets a fresh provider ID; reusing the expired one is forbidden.
    from app.modules.payments.gateway import CheckoutSession

    async def create_new(snapshot):
        gateway.created.append(snapshot.id)
        return CheckoutSession(
            "checkout-new", "https://sandbox.asaas.com/checkoutSession/show?id=checkout-new"
        )

    gateway.create_checkout = create_new
    second = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={})
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]
    assert len(gateway.created) == 2
