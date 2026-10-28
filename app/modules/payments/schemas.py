from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.validators import validate_brazilian_plate


class HistoryCheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plate: str

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return validate_brazilian_plate(value)


class SubscriptionCheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product: str
    vehicle_id: int | None
    amount_cents: int
    currency: str
    environment: str
    state: str
    checkout_url: str | None
    plate: str | None = None
    benefit_active: bool = False
    benefit_expires_at: datetime | None = None
    created_at: datetime


class SubscriptionCancellationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: str
    status: str
    requested_at: datetime
    confirmed_at: datetime | None


class SubscriptionPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    order_id: str
    starts_at: datetime
    expires_at: datetime


class SubscriptionRead(BaseModel):
    order_id: str
    cancellation_status: str | None


class SubscriptionSummaryRead(BaseModel):
    capacity_limit: int
    free_vehicle_id: int | None
    can_start_checkout: bool
    period: SubscriptionPeriodRead | None
    subscription: SubscriptionRead | None
