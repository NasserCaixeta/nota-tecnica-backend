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
