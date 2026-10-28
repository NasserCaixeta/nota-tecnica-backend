from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
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


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "environment", "event_id", name="uq_payment_event"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), default="asaas")
    environment: Mapped[str] = mapped_column(String(16), default="sandbox")
    event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(80))
    provider_payment_id: Mapped[str] = mapped_column(String(200), index=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerifiedPayment(Base):
    __tablename__ = "verified_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id"), index=True)
    provider_payment_id: Mapped[str] = mapped_column(String(200), unique=True)
    state: Mapped[str] = mapped_column(String(80))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HistoryAccessGrant(Base):
    __tablename__ = "history_access_grants"
    __table_args__ = (CheckConstraint("expires_at > starts_at", name="ck_history_access_range"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id"), unique=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("verified_payments.id"), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionPeriod(Base):
    __tablename__ = "subscription_periods"
    __table_args__ = (
        CheckConstraint("expires_at > starts_at", name="ck_subscription_period_range"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id"), index=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("verified_payments.id"), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider_subscription_id: Mapped[str] = mapped_column(String(200), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionCancellation(Base):
    __tablename__ = "subscription_cancellations"
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
