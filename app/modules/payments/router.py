from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.payments.asaas import AsaasGateway
from app.modules.auth.dependencies import get_approved_participant, get_current_user
from app.modules.payments.gateway import PaymentGateway
from app.modules.payments.models import PaymentProduct
from app.modules.payments.readers import order_read, payment_config_read, subscription_read
from app.modules.payments.schemas import (
    HistoryCheckoutCreate,
    PaymentOrderRead,
    SubscriptionCancellationRead,
    SubscriptionCheckoutCreate,
    SubscriptionSummaryRead,
)
from app.modules.payments.service import create_order, find_order, retry_order
from app.modules.users.models import User

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_gateway() -> PaymentGateway:
    settings = get_settings()
    if not settings.payments_enabled or not settings.asaas_api_key.get_secret_value():
        raise HTTPException(503, "Sandbox payment provider is not configured")
    return AsaasGateway(api_key=settings.asaas_api_key.get_secret_value())


Session = Annotated[AsyncSession, Depends(get_db)]
Participant = Annotated[User, Depends(get_approved_participant)]
Gateway = Annotated[PaymentGateway, Depends(get_payment_gateway)]


@router.post("/history-checkouts", response_model=PaymentOrderRead, status_code=201)
async def history_checkout(
    payload: HistoryCheckoutCreate, session: Session, buyer: Participant, gateway: Gateway
):
    return await order_read(
        session,
        await create_order(session, buyer, PaymentProduct.HISTORY_ACCESS, gateway, payload.plate),
    )


@router.post("/subscription-checkouts", response_model=PaymentOrderRead, status_code=201)
async def subscription_checkout(
    payload: SubscriptionCheckoutCreate, session: Session, buyer: Participant, gateway: Gateway
):
    return await order_read(
        session, await create_order(session, buyer, PaymentProduct.GARAGE_MONTHLY, gateway)
    )


@router.get("/orders/{order_id}", response_model=PaymentOrderRead)
async def read_order(
    order_id: str, session: Session, actor: Annotated[User, Depends(get_current_user)]
):
    return await order_read(session, await find_order(session, order_id, actor))


@router.post("/orders/{order_id}/retry", response_model=PaymentOrderRead)
async def retry_checkout(order_id: str, session: Session, buyer: Participant, gateway: Gateway):
    return await order_read(session, await retry_order(session, buyer, order_id, gateway))


from app.modules.payments.webhooks import router as webhook_router  # noqa: E402

router.include_router(webhook_router)


@router.post("/subscriptions/{order_id}/cancel", response_model=SubscriptionCancellationRead)
async def cancel_garage_subscription(
    order_id: str, session: Session, buyer: Participant, gateway: Gateway
):
    from app.modules.payments.cancellations import cancel_subscription

    return await cancel_subscription(session, buyer, order_id, gateway)


@router.get("/config")
async def read_payment_config():
    return payment_config_read()


@router.get("/subscription", response_model=SubscriptionSummaryRead)
async def read_garage_subscription(session: Session, buyer: Participant):
    return await subscription_read(session, buyer.id)
