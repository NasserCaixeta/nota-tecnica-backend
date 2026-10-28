import json
from datetime import UTC, datetime

import httpx
import pytest


async def test_asaas_checkout_contract_is_sandbox_and_contains_no_card_or_customer_data():
    from app.integrations.payments.asaas import AsaasGateway
    from app.modules.payments.gateway import CheckoutOrder

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "c7b1c696-b27b-4d3d-80b9-d1c018e387f8"})

    gateway = AsaasGateway(api_key="sandbox-test-key", transport=httpx.MockTransport(respond))
    session = await gateway.create_checkout(
        CheckoutOrder(
            id="opaque-order",
            product="garage_monthly",
            amount_cents=4900,
            currency="BRL",
            callback_url="https://pilot.test/app/compras/opaque-order",
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
        )
    )
    assert requests[0].url.host == "api-sandbox.asaas.com"
    body = json.loads(requests[0].content)
    assert body["externalReference"] == "opaque-order"
    assert body["chargeTypes"] == ["RECURRENT"]
    assert body["subscription"]["cycle"] == "MONTHLY"
    assert body["items"][0]["value"] == 49
    assert {"customerData", "creditCard", "creditCardHolderInfo"}.isdisjoint(body)
    assert session.url.startswith("https://sandbox.asaas.com/")


def test_asaas_gateway_rejects_production_hosts():
    from app.integrations.payments.asaas import AsaasGateway

    with pytest.raises(ValueError, match="Sandbox"):
        AsaasGateway(api_key="test", base_url="https://api.asaas.com/v3")


@pytest.mark.parametrize("status,body", [(500, {}), (408, {}), (200, {}), (200, {"id": None})])
async def test_asaas_inconclusive_creation_is_never_repeated(status, body):
    from app.integrations.payments.asaas import AsaasGateway
    from app.modules.payments.gateway import CheckoutOrder, GatewayUncertainOutcome

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, json=body)

    gateway = AsaasGateway(api_key="secret", transport=httpx.MockTransport(respond))
    order = CheckoutOrder(
        "order", "history_access", 1900, "BRL", "https://pilot.test", datetime.now(UTC)
    )
    with pytest.raises(GatewayUncertainOutcome):
        await gateway.create_checkout(order)
    assert await gateway.reconcile_checkout(order) is None
    assert len(requests) == 1
    assert "secret" not in str(GatewayUncertainOutcome())


async def test_asaas_detached_checkout_has_no_subscription():
    from app.integrations.payments.asaas import AsaasGateway
    from app.modules.payments.gateway import CheckoutOrder

    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test-checkout"})

    gateway = AsaasGateway(api_key="test", transport=httpx.MockTransport(respond))
    await gateway.create_checkout(
        CheckoutOrder(
            "order", "history_access", 1900, "BRL", "https://pilot.test", datetime.now(UTC)
        )
    )
    assert bodies[0]["chargeTypes"] == ["DETACHED"]
    assert bodies[0]["billingTypes"] == ["PIX", "CREDIT_CARD"]
    assert "subscription" not in bodies[0]


async def test_canonical_payment_loads_payer_and_verified_monthly_due_dates(monkeypatch):
    from app.core.config import get_settings
    from app.integrations.payments.asaas import AsaasGateway

    monkeypatch.setenv("ASAAS_EVENT_TIMEZONE", "America/Sao_Paulo")
    get_settings.cache_clear()
    paths = []

    def respond(request):
        paths.append(request.url.path)
        data = {
            "/v3/payments/pay_1": {
                "id": "pay_1",
                "status": "CONFIRMED",
                "value": 49,
                "customer": "cus_1",
                "subscription": "sub_1",
                "checkoutSession": "checkout_1",
                "externalReference": "order",
                "dueDate": "2026-10-01",
                "confirmedDate": "2026-10-01",
                "billingType": "CREDIT_CARD",
            },
            "/v3/customers/cus_1": {
                "id": "cus_1",
                "cpfCnpj": "529.982.247-25",
                "email": "buyer@example.com",
            },
            "/v3/subscriptions/sub_1": {
                "id": "sub_1",
                "cycle": "MONTHLY",
                "nextDueDate": "2026-11-01",
            },
        }[request.url.path]
        return httpx.Response(200, json=data)

    gateway = AsaasGateway(api_key="test", transport=httpx.MockTransport(respond))
    payment = await gateway.fetch_payment("pay_1")
    assert payment.customer_cpf == "52998224725"
    assert payment.customer_email == "buyer@example.com"
    assert payment.checkout_id == "checkout_1"
    assert payment.confirmed_at is None  # A calendar date is not a precise confirmation instant.
    assert payment.period_starts_at.isoformat() == "2026-10-01T00:00:00-03:00"
    assert payment.period_ends_at.isoformat() == "2026-11-01T00:00:00-03:00"
    assert len(paths) == 3
    get_settings.cache_clear()


async def test_missing_verified_next_due_date_does_not_invent_subscription_end(monkeypatch):
    from app.core.config import get_settings
    from app.integrations.payments.asaas import AsaasGateway

    monkeypatch.setenv("ASAAS_EVENT_TIMEZONE", "America/Sao_Paulo")
    get_settings.cache_clear()

    def respond(request):
        data = {
            "/v3/payments/pay_1": {
                "id": "pay_1",
                "status": "CONFIRMED",
                "value": 49,
                "customer": "cus_1",
                "subscription": "sub_1",
                "dueDate": "2026-10-01",
            },
            "/v3/customers/cus_1": {
                "id": "cus_1",
                "cpfCnpj": "52998224725",
                "email": "buyer@example.com",
            },
            "/v3/subscriptions/sub_1": {"id": "sub_1", "cycle": "MONTHLY"},
        }[request.url.path]
        return httpx.Response(200, json=data)

    gateway = AsaasGateway(api_key="test", transport=httpx.MockTransport(respond))
    payment = await gateway.fetch_payment("pay_1")
    assert payment.period_ends_at is None
    get_settings.cache_clear()


async def test_subscription_cancel_reconciles_before_delete_and_verifies_result():
    from app.integrations.payments.asaas import AsaasGateway

    requests = []

    def respond(request):
        requests.append(request.method)
        if len(requests) == 1:
            return httpx.Response(200, json={"id": "sub_1", "status": "ACTIVE"})
        if request.method == "DELETE":
            return httpx.Response(200, json={"id": "sub_1", "deleted": True})
        return httpx.Response(404)

    gateway = AsaasGateway(api_key="test", transport=httpx.MockTransport(respond))
    assert await gateway.cancel_subscription("sub_1") is True
    assert requests == ["GET", "DELETE", "GET"]


@pytest.mark.parametrize("body", [[], {"id": "pay_1", "customer": "cus_1", "value": "not-money"}])
async def test_malformed_canonical_response_is_a_safe_gateway_failure(body):
    from app.integrations.payments.asaas import AsaasGateway
    from app.modules.payments.gateway import GatewayUnavailable

    def respond(request):
        return httpx.Response(
            200, json={"id": "cus_1"} if "customers/" in request.url.path else body
        )

    gateway = AsaasGateway(api_key="secret", transport=httpx.MockTransport(respond))
    with pytest.raises(GatewayUnavailable):
        await gateway.fetch_payment("pay_1")
