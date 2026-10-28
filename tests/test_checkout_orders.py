import pytest

from app.core.config import get_settings
from tests.test_maintenance import auth_headers
from tests.test_maintenance_moderation import approve_customer_service


class CheckoutGateway:
    def __init__(self, uncertain=False):
        self.uncertain = uncertain
        self.created = []
        self.reconciled = []

    async def create_checkout(self, order):
        from app.modules.payments.gateway import CheckoutSession, GatewayUncertainOutcome

        self.created.append(order.id)
        if self.uncertain:
            raise GatewayUncertainOutcome()
        return CheckoutSession(
            "checkout-test-id", "https://sandbox.asaas.com/checkoutSession/show?id=checkout-test-id"
        )

    async def reconcile_checkout(self, order):
        from app.modules.payments.gateway import CheckoutSession

        self.reconciled.append(order.id)
        return CheckoutSession(
            "checkout-test-id", "https://sandbox.asaas.com/checkoutSession/show?id=checkout-test-id"
        )


@pytest.fixture
def checkout_gateway(client, monkeypatch):
    from app.modules.payments.router import get_payment_gateway

    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("PAYMENTS_HISTORY_PRICE_CENTS", "1900")
    monkeypatch.setenv("PAYMENTS_SUBSCRIPTION_PRICE_CENTS", "4900")
    monkeypatch.setenv("PAYMENTS_CALLBACK_BASE_URL", "https://pilot.test")
    get_settings.cache_clear()
    gateway = CheckoutGateway()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    yield gateway
    get_settings.cache_clear()


async def test_checkout_uses_server_price_and_creation_does_not_mark_paid(
    client, db_session, checkout_gateway
):
    await approve_customer_service(client, db_session)
    h = auth_headers(client, email="buyer@example.com", cpf="39053344705")
    bad = client.post(
        "/api/v1/payments/history-checkouts",
        headers=h,
        json={"plate": "ABC1D23", "amount_cents": 1},
    )
    assert bad.status_code == 422
    created = client.post(
        "/api/v1/payments/history-checkouts", headers=h, json={"plate": "ABC1D23"}
    )
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["amount_cents"] == 1900
    assert order["currency"] == "BRL"
    assert order["environment"] == "sandbox"
    assert order["state"] == "checkout_pending"
    repeated = client.post(
        "/api/v1/payments/history-checkouts", headers=h, json={"plate": "ABC1D23"}
    )
    assert repeated.json()["id"] == order["id"]
    assert len(checkout_gateway.created) == 1
    other = auth_headers(client, email="other@example.com", cpf="11144477735")
    assert client.get(f"/api/v1/payments/orders/{order['id']}", headers=other).status_code == 404


def test_checkout_rejects_missing_history_and_pending_participation(client, checkout_gateway):
    from tests.test_auth_users import login, register_user

    h = auth_headers(client)
    assert (
        client.post(
            "/api/v1/payments/history-checkouts", headers=h, json={"plate": "ABC1D23"}
        ).status_code
        == 409
    )
    register_user(client, email="pending@example.com", cpf="39053344705")
    pending = {"Authorization": f"Bearer {login(client, email='pending@example.com')}"}
    assert (
        client.post("/api/v1/payments/subscription-checkouts", headers=pending, json={}).status_code
        == 403
    )
    assert checkout_gateway.created == []


def test_uncertain_checkout_reuses_order_and_reconciles_without_second_creation(
    client, checkout_gateway
):
    checkout_gateway.uncertain = True
    h = auth_headers(client)
    created = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={})
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["state"] == "reconciliation_required"
    assert order["checkout_url"] is None
    retried = client.post(f"/api/v1/payments/orders/{order['id']}/retry", headers=h)
    assert retried.status_code == 200
    assert retried.json()["id"] == order["id"]
    assert retried.json()["state"] == "checkout_pending"
    assert checkout_gateway.created == checkout_gateway.reconciled
    assert len(checkout_gateway.created) == 1


@pytest.mark.parametrize(
    "variable,value",
    [
        ("PAYMENTS_ENABLED", "false"),
        ("PAYMENTS_CALLBACK_BASE_URL", "http://pilot.test"),
        ("PAYMENTS_CALLBACK_BASE_URL", "https://pilot.test/#untrusted"),
    ],
)
def test_checkout_requires_explicit_sandbox_configuration(
    client, checkout_gateway, monkeypatch, variable, value
):
    h = auth_headers(client)
    monkeypatch.setenv(variable, value)
    get_settings.cache_clear()
    result = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={})
    assert result.status_code == 503
    assert checkout_gateway.created == []


async def test_checkout_creation_cannot_expand_garage(client, db_session, checkout_gateway):
    from datetime import UTC, datetime

    from app.modules.garage.policy import get_garage_capacity
    from app.modules.payments.models import PaymentOrder

    h = auth_headers(client)
    response = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={})
    assert response.status_code == 201
    order = await db_session.get(PaymentOrder, response.json()["id"])
    capacity = await get_garage_capacity(db_session, order.buyer_id, datetime.now(UTC))
    assert capacity.limit == 1
    assert response.json()["state"] != "paid"
    assert (
        client.post(
            "/api/v1/payments/subscription-checkouts", headers=h, json={"limit": 100}
        ).status_code
        == 422
    )


async def test_checkout_response_cannot_overwrite_a_financial_confirmation(
    client, db_session, checkout_gateway
):
    from app.modules.payments.gateway import CheckoutSession
    from app.modules.payments.models import PaymentOrder

    async def confirm_before_returning(snapshot):
        order = await db_session.get(PaymentOrder, snapshot.id)
        order.state = "paid"
        await db_session.commit()
        return CheckoutSession(
            "checkout_1", "https://sandbox.asaas.com/checkoutSession/show?id=checkout_1"
        )

    checkout_gateway.create_checkout = confirm_before_returning
    response = client.post(
        "/api/v1/payments/subscription-checkouts", headers=auth_headers(client), json={}
    )
    assert response.status_code == 201
    assert response.json()["state"] == "paid"


async def test_existing_relationship_or_paid_access_prevents_second_purchase(
    client, db_session, checkout_gateway
):
    from sqlalchemy import select

    from app.modules.users.models import User
    from tests.test_paid_history_access import add_history_grant

    owner, vehicle_id, _, _, _, _ = await approve_customer_service(client, db_session)
    url = "/api/v1/payments/history-checkouts"
    assert client.post(url, headers=owner, json={"plate": "ABC1D23"}).status_code == 409
    buyer_headers = auth_headers(client, email="buyer@example.com", cpf="39053344705")
    buyer = await db_session.scalar(select(User).where(User.email == "buyer@example.com"))
    await add_history_grant(db_session, buyer.id, vehicle_id)
    assert client.post(url, headers=buyer_headers, json={"plate": "ABC1D23"}).status_code == 409
    assert checkout_gateway.created == []


async def test_expired_benefit_does_not_create_duplicate_remote_subscription(
    client, db_session, checkout_gateway
):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.modules.users.models import User
    from tests.test_garage_subscription import add_subscription_period

    h = auth_headers(client)
    buyer = await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    now = datetime.now(UTC)
    await add_subscription_period(
        db_session, buyer.id, now - timedelta(days=32), now - timedelta(days=1)
    )
    response = client.post("/api/v1/payments/subscription-checkouts", headers=h, json={})
    assert response.status_code == 409
    assert checkout_gateway.created == []
