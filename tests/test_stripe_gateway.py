from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest

from app.modules.payments.gateway import CheckoutOrder, GatewayUnavailable, GatewayUncertainOutcome

NOW = datetime.now(UTC)


def order(product="history_access", **kwargs):
    return CheckoutOrder(
        "order-one",
        product,
        1900,
        "BRL",
        "https://pilot.test/app/compras/order-one",
        kwargs.pop("created_at", NOW),
        buyer_id=1,
        buyer_email="driver@example.com",
        **kwargs,
    )


def customer():
    return {
        "id": "cus_one",
        "livemode": False,
        "email": "driver@example.com",
        "metadata": {"user_id": "1"},
    }


def intent(*, recurring=False, refunded=False):
    return {
        "id": "pi_one",
        "livemode": False,
        "status": "succeeded",
        "amount": 1900,
        "amount_received": 1900,
        "currency": "brl",
        "customer": "cus_one",
        "metadata": {} if recurring else {"order_id": "order-one", "product": "history_access"},
        "capture_method": "automatic",
        "latest_charge": {
            "id": "ch_one",
            "livemode": False,
            "payment_intent": "pi_one",
            "paid": True,
            "captured": True,
            "amount_refunded": 1900 if refunded else 0,
            "disputed": False,
            "balance_transaction": {"created": int(NOW.timestamp())},
        },
    }


def invoice():
    return {
        "id": "in_one",
        "livemode": False,
        "status": "paid",
        "amount_paid": 1900,
        "amount_due": 1900,
        "currency": "brl",
        "customer": "cus_one",
        "status_transitions": {"paid_at": int(NOW.timestamp())},
        "parent": {
            "type": "subscription_details",
            "subscription_details": {
                "subscription": "sub_one",
                "metadata": {"order_id": "order-one"},
            },
        },
        "lines": {
            "has_more": False,
            "data": [
                {
                    "amount": 1900,
                    "parent": {"type": "subscription_item_details"},
                    "pricing": {"price_details": {"price": "price_one"}},
                    "period": {"start": 1790812800, "end": 1793491200},
                }
            ],
        },
    }


def invoice_payment():
    return {
        "id": "inpay_one",
        "livemode": False,
        "invoice": "in_one",
        "status": "paid",
        "amount_paid": 1900,
        "payment": {"type": "payment_intent", "payment_intent": "pi_one"},
    }


@pytest.mark.parametrize("product", ["history_access", "garage_monthly"])
async def test_checkout_server_metadata_price_version_and_stable_idempotency(product):
    from app.integrations.payments.stripe import StripeGateway

    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.host == "api.stripe.com"
        assert request.headers["Stripe-Version"] == "2026-10-28.endive"
        if request.url.path.endswith("/customers"):
            return httpx.Response(200, json=customer())
        return httpx.Response(
            200,
            json={
                "id": "cs_test_one",
                "livemode": False,
                "url": "https://checkout.stripe.com/c/pay/cs_test_one",
                "client_reference_id": "order-one",
            },
        )

    gateway = StripeGateway(api_key="sk_test_private", transport=httpx.MockTransport(respond))
    first = await gateway.create_checkout(order(product))
    second = await gateway.reconcile_checkout(order(product))
    checkouts = [r for r in requests if r.url.path.endswith("/checkout/sessions")]
    assert len(checkouts) == 2
    assert checkouts[0].headers["Idempotency-Key"] == checkouts[1].headers["Idempotency-Key"]
    assert checkouts[0].content == checkouts[1].content
    body = parse_qs(checkouts[0].content.decode())
    assert body["line_items[0][price_data][unit_amount]"] == ["1900"]
    assert body["client_reference_id"] == ["order-one"]
    assert body["payment_method_types[0]"] == ["card"]
    assert body["mode"] == ["subscription" if product == "garage_monthly" else "payment"]
    prefix = "subscription_data" if product == "garage_monthly" else "payment_intent_data"
    assert body[prefix + "[metadata][order_id]"] == ["order-one"]
    assert ("line_items[0][price_data][recurring][interval]" in body) == (
        product == "garage_monthly"
    )
    assert b"cpf" not in checkouts[0].content and b"card[number]" not in checkouts[0].content
    assert first == second


@pytest.mark.parametrize("key", ["sk_live_secret", "rk_live_secret", "pk_test_public", ""])
def test_gateway_rejects_non_test_secret_keys(key):
    from app.integrations.payments.stripe import StripeGateway

    with pytest.raises(ValueError):
        StripeGateway(api_key=key)


async def test_reconciliation_cannot_repeat_creation_after_idempotency_retention():
    from app.integrations.payments.stripe import StripeGateway

    requests = []
    gateway = StripeGateway(
        api_key="sk_test_private", transport=httpx.MockTransport(lambda r: requests.append(r))
    )
    assert await gateway.reconcile_checkout(order(created_at=NOW - timedelta(hours=24))) is None
    assert requests == []


async def test_uncertain_stripe_response_is_sanitized_and_not_a_definite_rejection():
    from app.integrations.payments.stripe import StripeGateway

    def respond(request):
        if request.url.path.endswith("/customers"):
            return httpx.Response(200, json=customer())
        return httpx.Response(500, text="provider-private-payload")

    with pytest.raises(GatewayUncertainOutcome) as error:
        await StripeGateway(
            api_key="sk_test_private", transport=httpx.MockTransport(respond)
        ).create_checkout(order())
    assert "private-payload" not in str(error.value)


async def test_one_off_payment_uses_canonical_capture_time_and_customer_owner():
    from app.integrations.payments.stripe import StripeGateway

    def respond(r):
        data = customer() if r.url.path.endswith("/cus_one") else intent()
        return httpx.Response(200, json=data)

    result = await StripeGateway(
        api_key="sk_test_private", transport=httpx.MockTransport(respond)
    ).fetch_payment("pi_one")
    assert result.id == "pi_one" and result.customer_user_reference == "1"
    assert result.customer_email == "driver@example.com"
    assert result.confirmed_at == datetime.fromtimestamp(int(NOW.timestamp()), UTC)
    assert result.state == "CONFIRMED" and result.amount_cents == 1900


@pytest.mark.parametrize("refunded", [False, True])
async def test_subscription_invoice_period_and_refund_pi_use_same_canonical_receipt(refunded):
    from app.integrations.payments.stripe import StripeGateway

    requests = []

    def respond(r):
        requests.append(r)
        path = r.url.path
        if path.endswith("/in_one"):
            data = invoice()
        elif path.endswith("/pi_one"):
            data = intent(recurring=True, refunded=refunded)
        elif path.endswith("/invoice_payments"):
            data = {"data": [invoice_payment()], "has_more": False}
        elif path.endswith("/price_one"):
            data = {
                "id": "price_one",
                "livemode": False,
                "recurring": {"interval": "month", "interval_count": 1},
            }
        elif path.endswith("/cus_one"):
            data = customer()
        else:
            raise AssertionError(path)
        return httpx.Response(200, json=data)

    gateway = StripeGateway(api_key="sk_test_private", transport=httpx.MockTransport(respond))
    result = await gateway.fetch_payment("pi_one" if refunded else "in_one")
    assert result.id == "in_one" and result.subscription_id == "sub_one"
    assert result.source_id == ("pi_one" if refunded else "in_one")
    assert result.period_starts_at == datetime.fromtimestamp(1790812800, UTC)
    assert result.period_ends_at == datetime.fromtimestamp(1793491200, UTC)
    assert result.state == ("REFUNDED" if refunded else "CONFIRMED")
    assert all("/subscriptions/" not in str(r.url) for r in requests)


async def test_live_canonical_objects_are_never_accepted():
    from app.integrations.payments.stripe import StripeGateway

    def respond(r):
        return httpx.Response(200, json={**intent(), "livemode": True})

    with pytest.raises(GatewayUnavailable):
        await StripeGateway(
            api_key="sk_test_private", transport=httpx.MockTransport(respond)
        ).fetch_payment("pi_one")


async def test_cancel_subscription_disables_renewal_without_deleting_paid_period():
    from app.integrations.payments.stripe import StripeGateway

    requests = []

    def respond(r):
        requests.append(r)
        return httpx.Response(
            200,
            json={
                "id": "sub_one",
                "livemode": False,
                "status": "active",
                "cancel_at_period_end": r.method == "POST",
            },
        )

    result = await StripeGateway(
        api_key="sk_test_private", transport=httpx.MockTransport(respond)
    ).cancel_subscription("sub_one")
    assert result is True
    assert [r.method for r in requests] == ["GET", "POST"]
    assert parse_qs(requests[-1].content.decode())["cancel_at_period_end"] == ["true"]
