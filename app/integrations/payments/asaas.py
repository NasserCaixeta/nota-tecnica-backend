from decimal import Decimal
from urllib.parse import quote

import httpx

from app.modules.payments.gateway import (
    CheckoutOrder,
    CheckoutSession,
    GatewayUnavailable,
    GatewayUncertainOutcome,
    ProviderPayment,
)

SANDBOX_API = "https://api-sandbox.asaas.com/v3"


class AsaasGateway:
    def __init__(self, *, api_key: str, base_url: str = SANDBOX_API, transport=None):
        if base_url.rstrip("/") != SANDBOX_API:
            raise ValueError("Only the Asaas Sandbox API is allowed")
        self.api_key = api_key
        self.base_url = SANDBOX_API
        self.transport = transport

    def client(self):
        return httpx.AsyncClient(
            base_url=self.base_url + "/",
            timeout=20,
            follow_redirects=False,
            headers={"access_token": self.api_key, "User-Agent": "NotaTecnica-Pilot/1.0"},
            transport=self.transport,
        )

    async def create_checkout(self, order: CheckoutOrder) -> CheckoutSession:
        recurring = order.product == "garage_monthly"
        payload = {
            "billingTypes": ["CREDIT_CARD"] if recurring else ["PIX", "CREDIT_CARD"],
            "chargeTypes": ["RECURRENT"] if recurring else ["DETACHED"],
            "minutesToExpire": 60,
            "externalReference": order.id,
            "callback": {
                key: order.callback_url for key in ("successUrl", "cancelUrl", "expiredUrl")
            },
            "items": [
                {
                    "name": "Garagem mensal" if recurring else "Histórico por placa",
                    "description": "Ambiente de testes — sem cobrança real",
                    "quantity": 1,
                    "value": order.amount_cents / 100,
                }
            ],
        }
        if recurring:
            payload["subscription"] = {
                "cycle": "MONTHLY",
                "nextDueDate": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        try:
            async with self.client() as client:
                response = await client.post("checkouts", json=payload)
        except httpx.HTTPError:
            raise GatewayUncertainOutcome() from None
        if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
            raise GatewayUnavailable()
        if not response.is_success:
            raise GatewayUncertainOutcome()
        try:
            provider_id = response.json()["id"]
            if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise GatewayUncertainOutcome() from None
        return CheckoutSession(
            provider_id,
            "https://sandbox.asaas.com/checkoutSession/show?id=" + quote(provider_id, safe=""),
        )

    async def reconcile_checkout(self, order: CheckoutOrder) -> CheckoutSession | None:
        # Asaas does not document a checkout lookup by externalReference. An uncertain
        # creation remains pending until provider reconciliation; never create again.
        return None

    async def fetch_payment(self, provider_payment_id: str) -> ProviderPayment:
        try:
            async with self.client() as client:
                response = await client.get("payments/" + quote(provider_payment_id, safe=""))
                response.raise_for_status()
                data = response.json()
            amount = Decimal(str(data["value"])) * 100
            if amount != amount.to_integral_value():
                raise ValueError()
            return ProviderPayment(
                id=data["id"],
                state=data["status"],
                order_reference=data.get("externalReference"),
                amount_cents=int(amount),
                currency="BRL",
                customer_id=data["customer"],
                subscription_id=data.get("subscription"),
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise GatewayUnavailable() from None
