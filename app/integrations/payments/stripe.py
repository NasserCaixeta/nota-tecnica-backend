"""Stripe Checkout, strictly test credentials and canonical test resources."""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit

import httpx

from app.modules.payments.gateway import (
    CheckoutOrder,
    CheckoutSession,
    GatewayUnavailable,
    GatewayUncertainOutcome,
    ProviderPayment,
)

STRIPE_API_VERSION = "2026-10-28.endive"


def test_secret(value):
    return value.startswith(("sk_test_", "rk_test_", "rkcs_test_"))


def timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, UTC)


def resource_id(value):
    return value.get("id") if isinstance(value, dict) else value


def checkout_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "checkout.stripe.com"
        or not parsed.path.startswith("/c/pay/cs_test_")
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Invalid Stripe test checkout URL")
    return value


class StripeGateway:
    def __init__(self, *, api_key: str, transport=None):
        if not test_secret(api_key):
            raise ValueError("Stripe test secret key required")
        self.api_key = api_key
        self.transport = transport

    def client(self):
        return httpx.AsyncClient(
            base_url="https://api.stripe.com/v1/",
            timeout=20,
            follow_redirects=False,
            transport=self.transport,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Stripe-Version": STRIPE_API_VERSION,
            },
        )

    async def request(self, method, path, *, data=None, params=None, key=None, missing_ok=False):
        try:
            async with self.client() as client:
                response = await client.request(
                    method,
                    path,
                    data=data,
                    params=params,
                    headers={"Idempotency-Key": key} if key else None,
                )
            if missing_ok and response.status_code == 404:
                return None
            if response.status_code >= 500 and method == "POST":
                raise GatewayUncertainOutcome()
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError()
            if "data" not in result and result.get("livemode") is not False:
                raise ValueError()
            return result
        except (httpx.TimeoutException, httpx.NetworkError):
            if method == "POST":
                raise GatewayUncertainOutcome() from None
            raise GatewayUnavailable() from None
        except (httpx.HTTPError, ValueError, TypeError):
            raise GatewayUnavailable() from None

    async def get(self, kind, identity, **kwargs):
        if not isinstance(identity, str) or not identity or len(identity) > 200:
            raise GatewayUnavailable()
        result = await self.request("GET", kind + "/" + quote(identity, safe=""), **kwargs)
        if result is not None and result.get("id") != identity:
            raise GatewayUnavailable()
        return result

    def session(self, data, order):
        if data.get("client_reference_id") != order.id:
            raise GatewayUnavailable()
        try:
            if not data["id"].startswith("cs_test_"):
                raise ValueError()
            return CheckoutSession(data["id"], checkout_url(data["url"]))
        except (ValueError, KeyError, TypeError):
            raise GatewayUnavailable() from None

    async def create_checkout(self, order: CheckoutOrder):
        if order.buyer_id is None or not order.buyer_email:
            raise GatewayUnavailable()
        customer = await self.request(
            "POST",
            "customers",
            data={
                "email": order.buyer_email,
                "metadata[user_id]": str(order.buyer_id),
            },
            # Align customer and Checkout retention windows. An older user-wide
            # key may expire while this order's uncertain Checkout is retried.
            key="nt:customer:" + order.id,
        )
        recurring = order.product == "garage_monthly"
        prefix = "subscription_data" if recurring else "payment_intent_data"
        data = {
            "mode": "subscription" if recurring else "payment",
            "customer": customer["id"],
            "client_reference_id": order.id,
            "success_url": order.callback_url,
            "cancel_url": order.callback_url,
            "payment_method_types[0]": "card",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": order.currency.lower(),
            "line_items[0][price_data][unit_amount]": str(order.amount_cents),
            "line_items[0][price_data][product_data][name]": "Garagem mensal - cinco vagas"
            if recurring
            else "Historico por 30 dias",
            "metadata[order_id]": order.id,
            f"{prefix}[metadata][order_id]": order.id,
            f"{prefix}[metadata][product]": order.product,
        }
        if recurring:
            data["line_items[0][price_data][recurring][interval]"] = "month"
        else:
            data["payment_intent_data[capture_method]"] = "automatic"
        result = await self.request(
            "POST", "checkout/sessions", data=data, key="nt:checkout:" + order.id
        )
        return self.session(result, order)

    async def reconcile_checkout(self, order):
        if order.checkout_id:
            return self.session(await self.get("checkout/sessions", order.checkout_id), order)
        created = (
            order.created_at.replace(tzinfo=UTC)
            if order.created_at.tzinfo is None
            else order.created_at
        )
        if datetime.now(UTC) - created >= timedelta(hours=23):
            return None
        return await self.create_checkout(order)

    async def owner(self, customer_id, *, reversed_payment=False):
        try:
            data = await self.get("customers", customer_id)
            return data.get("email"), data.get("metadata", {}).get("user_id")
        except GatewayUnavailable:
            if reversed_payment:
                return None, None
            raise

    @staticmethod
    def financial_state(intent, charge):
        if charge.get("amount_refunded", 0) > 0 or charge.get("disputed"):
            return "REFUNDED"
        if intent.get("status") == "succeeded" and charge.get("paid") and charge.get("captured"):
            return "CONFIRMED"
        if intent.get("status") == "canceled":
            return "CANCELLED"
        return "PENDING"

    async def canonical_intent(self, identity):
        data = await self.get(
            "payment_intents", identity, params={"expand[]": "latest_charge.balance_transaction"}
        )
        charge = data.get("latest_charge") or {}
        if isinstance(charge, str):
            charge = await self.get("charges", charge, params={"expand[]": "balance_transaction"})
        if charge and (
            charge.get("livemode") is not False
            or resource_id(charge.get("payment_intent")) != identity
        ):
            raise GatewayUnavailable()
        return data, charge

    async def fetch_payment(self, provider_payment_id):
        try:
            if provider_payment_id.startswith("in_"):
                return await self.invoice_payment(provider_payment_id, provider_payment_id)
            source = provider_payment_id
            if source.startswith("ch_"):
                charge = await self.get("charges", source)
                provider_payment_id = resource_id(charge.get("payment_intent"))
            if not provider_payment_id or not provider_payment_id.startswith("pi_"):
                raise GatewayUnavailable()
            data, charge = await self.canonical_intent(provider_payment_id)
            metadata = data.get("metadata", {})
            if metadata.get("product") != "history_access":
                payments = await self.request(
                    "GET",
                    "invoice_payments",
                    params={
                        "payment[type]": "payment_intent",
                        "payment[payment_intent]": data["id"],
                        "limit": 2,
                    },
                )
                identities = {resource_id(p["invoice"]) for p in payments["data"]}
                if payments.get("has_more") or len(identities) != 1:
                    raise GatewayUnavailable()
                return await self.invoice_payment(identities.pop(), source)
            state = self.financial_state(data, charge)
            email, user_id = await self.owner(
                resource_id(data["customer"]), reversed_payment=state == "REFUNDED"
            )
            transaction = charge.get("balance_transaction") or {}
            if isinstance(transaction, str):
                transaction = await self.get("balance_transactions", transaction)
            return ProviderPayment(
                id=data["id"],
                state=state,
                source_id=source,
                order_reference=metadata.get("order_id"),
                amount_cents=data.get("amount_received") or data["amount"],
                currency=data["currency"].upper(),
                customer_id=resource_id(data["customer"]),
                customer_email=email,
                customer_user_reference=user_id,
                confirmed_at=timestamp(transaction.get("created"))
                if state == "CONFIRMED"
                else None,
                billing_type="CARD",
            )
        except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError):
            raise GatewayUnavailable() from None

    async def invoice_payment(self, identity, source):
        invoice = await self.get("invoices", identity)
        details = invoice.get("parent", {}).get("subscription_details", {})
        subscription_id = resource_id(details.get("subscription"))
        if not subscription_id:
            raise GatewayUnavailable()
        lines = invoice["lines"]
        if lines.get("has_more") or len(lines["data"]) != 1:
            raise GatewayUnavailable()
        line = lines["data"][0]
        if line.get("parent", {}).get("type") != "subscription_item_details":
            raise GatewayUnavailable()
        price = await self.get("prices", resource_id(line["pricing"]["price_details"]["price"]))
        recurring = price.get("recurring") or {}
        if recurring.get("interval") != "month" or recurring.get("interval_count", 1) != 1:
            raise GatewayUnavailable()
        payments = await self.request(
            "GET", "invoice_payments", params={"invoice": identity, "limit": 2}
        )
        if payments.get("has_more") or len(payments["data"]) != 1:
            raise GatewayUnavailable()
        payment = payments["data"][0]
        if payment.get("livemode") is not False or resource_id(payment["invoice"]) != identity:
            raise GatewayUnavailable()
        data, charge = await self.canonical_intent(
            resource_id(payment["payment"]["payment_intent"])
        )
        if resource_id(data["customer"]) != resource_id(invoice["customer"]):
            raise GatewayUnavailable()
        state = self.financial_state(data, charge)
        if state == "CONFIRMED" and (
            invoice["status"] != "paid"
            or payment["status"] != "paid"
            or payment["amount_paid"] != invoice["amount_paid"]
            or data["amount_received"] != invoice["amount_paid"]
            or line["amount"] != invoice["amount_paid"]
        ):
            state = "PENDING"
        email, user_id = await self.owner(
            resource_id(invoice["customer"]), reversed_payment=state == "REFUNDED"
        )
        return ProviderPayment(
            id=invoice["id"],
            source_id=source,
            state=state,
            order_reference=details.get("metadata", {}).get("order_id"),
            amount_cents=invoice["amount_paid"],
            currency=invoice["currency"].upper(),
            customer_id=resource_id(invoice["customer"]),
            customer_email=email,
            customer_user_reference=user_id,
            subscription_id=subscription_id,
            confirmed_at=timestamp(invoice["status_transitions"].get("paid_at")),
            billing_type="CARD",
            period_starts_at=timestamp(line["period"]["start"]),
            period_ends_at=timestamp(line["period"]["end"]),
        )

    async def cancel_subscription(self, provider_subscription_id):
        path = "subscriptions/" + quote(provider_subscription_id, safe="")
        data = await self.get("subscriptions", provider_subscription_id, missing_ok=True)
        if data is None or data.get("status") == "canceled" or data.get("cancel_at_period_end"):
            return True
        data = await self.request(
            "POST",
            path,
            data={"cancel_at_period_end": "true"},
            key="nt:cancel:" + provider_subscription_id,
        )
        return (
            data.get("id") == provider_subscription_id and data.get("cancel_at_period_end") is True
        )
