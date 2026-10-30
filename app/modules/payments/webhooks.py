"""Stripe signed raw-body inbox. No redirect or unverified payload grants access."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.payments.configuration import webhook_configuration_ready
from app.modules.payments.models import CheckoutEvent, PaymentEvent

router = APIRouter()


def dispatch_payment_event(event_id):
    from app.integrations.queue.payment_tasks import process_payment_event_task

    process_payment_event_task.delay(event_id)


def dispatch_checkout_event(event_id):
    from app.integrations.queue.payment_tasks import process_checkout_event_task

    process_checkout_event_task.delay(event_id)


class Event(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=100)
    created: int = Field(ge=0, strict=True)
    data: dict


def verify_signature(body, header, secret):
    try:
        fields = [part.strip().split("=", 1) for part in (header or "").split(",")]
        times = [value for key, value in fields if key == "t"]
        signatures = [value for key, value in fields if key == "v1"]
        if len(times) != 1 or abs(time.time() - int(times[0])) > 300:
            return False
        expected = hmac.new(
            secret.encode(), times[0].encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return any(hmac.compare_digest(expected, value) for value in signatures)
    except (ValueError, TypeError):
        return False


async def persist(session, event, dispatch):
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        model = type(event)
        event = await session.scalar(
            select(model).where(
                model.provider == "stripe",
                model.environment == "sandbox",
                model.event_id == event.event_id,
            )
        )
        if event is None:
            raise
    try:
        dispatch(event.id)
    except Exception:
        pass  # Durable inbox is retried by beat after broker failure.


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
):
    settings = get_settings()
    if not webhook_configuration_ready(settings):
        raise HTTPException(503, "Stripe test webhook is not configured")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 128 * 1024:
            raise HTTPException(413, "Webhook payload too large")
    if not verify_signature(
        bytes(body), signature, settings.stripe_webhook_secret.get_secret_value()
    ):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        raw = json.loads(body)
        if not isinstance(raw, dict) or raw.get("livemode") is not False:
            raise ValueError()
        event = Event.model_validate(raw)
        obj = event.data["object"]
        identity = obj["id"]
        if not isinstance(identity, str) or not 1 <= len(identity) <= 200:
            raise ValueError()
        when = datetime.fromtimestamp(event.created, UTC)
    except (ValueError, TypeError, KeyError, ValidationError, OverflowError):
        raise HTTPException(422, "Invalid Stripe test event") from None
    kind = event.type
    payment_id, internal = None, "PAYMENT_CONFIRMED"
    if kind.startswith("checkout.session."):
        states = {
            "checkout.session.completed": "CHECKOUT_PAID",
            "checkout.session.async_payment_succeeded": "CHECKOUT_PAID",
            "checkout.session.async_payment_failed": "CHECKOUT_CANCELED",
            "checkout.session.expired": "CHECKOUT_EXPIRED",
        }
        if kind not in states:
            return {"received": True}
        await persist(
            session,
            CheckoutEvent(
                provider="stripe",
                environment="sandbox",
                event_id=event.id,
                event_type=states[kind],
                provider_checkout_id=identity,
                order_reference=obj.get("client_reference_id"),
            ),
            dispatch_checkout_event,
        )
        if obj.get("mode") == "payment" and kind in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
        }:
            payment_id = obj.get("payment_intent")
    elif kind in {"invoice.paid", "invoice.payment_failed", "invoice.voided"}:
        payment_id = identity
    elif kind in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:
        if obj.get("metadata", {}).get("product") == "history_access":
            payment_id = identity
    elif kind == "charge.refunded":
        payment_id = identity
        internal = "PAYMENT_REFUNDED"
    elif kind in {"charge.dispute.created", "charge.dispute.closed"}:
        payment_id = obj.get("charge")
        internal = "PAYMENT_REFUNDED"
    if payment_id:
        if not isinstance(payment_id, str) or len(payment_id) > 200:
            raise HTTPException(422, "Invalid payment identity")
        # Only authenticated success events can be the fallback confirmation time.
        if kind not in {
            "payment_intent.succeeded",
            "invoice.paid",
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
        }:
            when = None
            if internal != "PAYMENT_REFUNDED":
                internal = "PAYMENT_PENDING"
        await persist(
            session,
            PaymentEvent(
                provider="stripe",
                environment="sandbox",
                event_id=event.id,
                event_type=internal,
                provider_payment_id=payment_id,
                provider_created_at=when,
            ),
            dispatch_payment_event,
        )
    return {"received": True}
