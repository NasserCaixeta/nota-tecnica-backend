from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.payments.checkout_events import CHECKOUT_TYPES
from app.modules.payments.configuration import webhook_configuration_ready
from app.modules.payments.models import CheckoutEvent, PaymentEvent

router = APIRouter()


def dispatch_payment_event(event_id: int):
    from app.integrations.queue.payment_tasks import process_payment_event_task

    process_payment_event_task.delay(event_id)


def parse_event_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            timezone = get_settings().asaas_event_timezone
            if not timezone or len(value) < 19:
                return None
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed.astimezone(UTC)
    except (ValueError, ZoneInfoNotFoundError):
        return None


class WebhookPayment(BaseModel):
    id: str = Field(min_length=1, max_length=200)


class WebhookCheckout(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    externalReference: str | None = Field(default=None, max_length=200)


class WebhookEvent(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    event: str = Field(min_length=1, max_length=80)
    dateCreated: str | None = Field(default=None, max_length=80)
    payment: WebhookPayment | None = None
    checkout: WebhookCheckout | None = None


@router.post("/webhooks/asaas")
async def asaas_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Header(alias="asaas-access-token")] = None,
):
    settings = get_settings()
    secret = settings.asaas_webhook_token.get_secret_value()
    if not webhook_configuration_ready(settings):
        raise HTTPException(503, "Sandbox webhook is not configured with a separate token")
    if token is None or not compare_digest(token.encode(), secret.encode()):
        raise HTTPException(401, "Invalid webhook authentication")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 128 * 1024:
            raise HTTPException(413, "Webhook payload too large")
    try:
        payload = WebhookEvent.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid webhook event") from None
    if payload.event in CHECKOUT_TYPES:
        if payload.checkout is None:
            raise HTTPException(422, "Checkout id is required")
        event = CheckoutEvent(
            provider="asaas",
            environment="sandbox",
            event_id=payload.id,
            event_type=payload.event,
            provider_checkout_id=payload.checkout.id,
            order_reference=payload.checkout.externalReference,
        )
        model = CheckoutEvent
        dispatch = dispatch_checkout_event
    elif payload.event.startswith("PAYMENT_"):
        if payload.payment is None:
            raise HTTPException(422, "Payment id is required")
        event = PaymentEvent(
            provider="asaas",
            environment="sandbox",
            event_id=payload.id,
            event_type=payload.event,
            provider_payment_id=payload.payment.id,
            provider_created_at=parse_event_time(payload.dateCreated),
        )
        model = PaymentEvent
        dispatch = dispatch_payment_event
    else:
        return {"received": True}
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        event = await session.scalar(
            select(model).where(
                model.provider == "asaas",
                model.environment == "sandbox",
                model.event_id == payload.id,
            )
        )
        if event is None:
            raise
    try:
        dispatch(event.id)
    except Exception:
        # The durable inbox is the source of truth. Beat recovers events after a
        # broker outage, including a crash between commit and dispatch.
        pass
    return {"received": True}


def dispatch_checkout_event(event_id: int):
    from app.integrations.queue.payment_tasks import process_checkout_event_task

    process_checkout_event_task.delay(event_id)
