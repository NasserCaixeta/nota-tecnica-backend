from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.modules.users.models import User
from tests.test_garage_subscription import add_subscription_period
from tests.test_maintenance import auth_headers


def test_payment_config_exposes_explicit_test_prices_without_credentials(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("PAYMENTS_HISTORY_PRICE_CENTS", "1900")
    monkeypatch.setenv("PAYMENTS_SUBSCRIPTION_PRICE_CENTS", "4900")
    monkeypatch.setenv("PAYMENTS_CALLBACK_BASE_URL", "https://pilot.test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv(
        "STRIPE_WEBHOOK_SECRET", "whsec_separate-webhook-secret-at-least-32-characters"
    )
    get_settings.cache_clear()
    response = client.get("/api/v1/payments/config")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["history_price_cents"] == 1900
    assert body["subscription_price_cents"] == 4900
    assert body["history_access_hours"] == 720
    assert body["garage_total_limit"] == 5
    assert body["environment"] == "sandbox"
    assert "secret" not in response.text
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    get_settings.cache_clear()
    assert client.get("/api/v1/payments/config").json()["enabled"] is False
    get_settings.cache_clear()


async def test_subscription_summary_and_order_report_actual_benefit(client, db_session):
    h = auth_headers(client)
    buyer = await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    now = datetime.now(UTC)
    await add_subscription_period(
        db_session, buyer.id, now - timedelta(days=1), now + timedelta(days=30)
    )
    response = client.get("/api/v1/payments/subscription", headers=h)
    assert response.status_code == 200
    body = response.json()
    assert body["capacity_limit"] == 5
    assert body["can_start_checkout"] is False
    assert body["period"]["order_id"] == "subscription-order"
    order = client.get("/api/v1/payments/orders/subscription-order", headers=h).json()
    assert order["benefit_active"] is True
    assert order["benefit_expires_at"] is not None
    assert "provider_subscription_id" not in order
