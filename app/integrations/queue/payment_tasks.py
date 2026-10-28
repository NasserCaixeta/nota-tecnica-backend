import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.integrations.payments.asaas import AsaasGateway
from app.integrations.queue.celery_app import celery_app
from app.modules.payments.events import pending_payment_event_ids, process_payment_event


async def process(event_id: int):
    settings = get_settings()
    if not settings.payments_enabled or not settings.asaas_api_key.get_secret_value():
        return
    gateway = AsaasGateway(api_key=settings.asaas_api_key.get_secret_value())
    # Each Celery invocation owns its asyncio loop; do not reuse a pooled engine
    # from another asyncio.run invocation in the same worker process.
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await process_payment_event(session, event_id, gateway, datetime.now(UTC))
    finally:
        await engine.dispose()


@celery_app.task(name="payments.process_event", ignore_result=True)
def process_payment_event_task(event_id: int):
    asyncio.run(process(event_id))


async def recover():
    if not get_settings().payments_enabled:
        return []
    engine = create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await pending_payment_event_ids(session)
    finally:
        await engine.dispose()


@celery_app.task(name="payments.recover_pending", ignore_result=True)
def recover_pending_payment_events():
    for event_id in asyncio.run(recover()):
        process_payment_event_task.delay(event_id)
