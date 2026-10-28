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
    from app.modules.payments.models import PaymentEvent

    monkeypatch.setattr(webhooks, "dispatch_payment_event", lambda _: None)
    response = client.post(
        "/api/v1/payments/webhooks/asaas",
        headers=webhook_setup,
        json={"id": "checkout_event", "event": "CHECKOUT_PAID", "checkout": {"id": "checkout_1"}},
    )
    assert response.status_code == 200
    assert await db_session.scalar(select(PaymentEvent)) is None
