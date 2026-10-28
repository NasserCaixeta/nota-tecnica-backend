from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CheckoutOrder:
    id: str
    product: str
    amount_cents: int
    currency: str
    callback_url: str
    created_at: datetime


@dataclass(frozen=True)
class CheckoutSession:
    provider_id: str
    url: str


@dataclass(frozen=True)
class ProviderPayment:
    id: str
    state: str
    order_reference: str | None
    amount_cents: int
    currency: str
    customer_id: str
    subscription_id: str | None = None
    confirmed_at: datetime | None = None
    customer_cpf: str | None = None
    customer_email: str | None = None
    checkout_id: str | None = None
    billing_type: str | None = None
    period_starts_at: datetime | None = None
    period_ends_at: datetime | None = None


class GatewayUncertainOutcome(RuntimeError):
    """The provider may have created a checkout. Never repeat the POST blindly."""


class GatewayUnavailable(RuntimeError):
    """A definite rejection, without exposing the provider's response or credentials."""


class PaymentGateway(Protocol):
    async def create_checkout(self, order: CheckoutOrder) -> CheckoutSession: ...
    async def reconcile_checkout(self, order: CheckoutOrder) -> CheckoutSession | None: ...
    async def fetch_payment(self, provider_payment_id: str) -> ProviderPayment: ...
    async def cancel_subscription(self, provider_subscription_id: str) -> bool: ...


PAYMENT_REVERSED_STATES = frozenset(
    {
        "REFUNDED",
        "REFUND_REQUESTED",
        "REFUND_IN_PROGRESS",
        "PARTIALLY_REFUNDED",
        "CHARGEBACK_REQUESTED",
        "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL",
    }
)
