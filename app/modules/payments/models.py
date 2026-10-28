from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentProduct(StrEnum):
    HISTORY_ACCESS = "history_access"
    GARAGE_MONTHLY = "garage_monthly"


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payment_positive_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_payment_currency"),
        CheckConstraint("environment = 'sandbox'", name="ck_payment_sandbox"),
        CheckConstraint(
            "product IN ('history_access', 'garage_monthly')", name="ck_payment_product"
        ),
        CheckConstraint(
            "(product = 'history_access' AND vehicle_id IS NOT NULL) OR "
            "(product = 'garage_monthly' AND vehicle_id IS NULL)",
            name="ck_payment_target",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product: Mapped[str] = mapped_column(String(32))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    amount_cents: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    environment: Mapped[str] = mapped_column(String(16), default="sandbox")
    state: Mapped[str] = mapped_column(String(32), default="created")
    provider_checkout_id: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(200), unique=True, nullable=True
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    callback_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
