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
    created_at: datetime
