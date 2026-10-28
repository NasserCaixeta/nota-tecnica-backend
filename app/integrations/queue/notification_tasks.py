import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.integrations.email.smtp import SMTPEmailSender
from app.integrations.queue.celery_app import celery_app
from app.modules.notifications.delivery import pending_delivery_ids, process_notification_delivery


async def deliver(delivery_id: int):
    settings = get_settings()
    if not settings.smtp_enabled:
        return
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await process_notification_delivery(
                session, delivery_id, SMTPEmailSender(), datetime.now(UTC)
            )
    finally:
        await engine.dispose()


async def pending():
    settings = get_settings()
    if not settings.smtp_enabled:
        return []
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await pending_delivery_ids(session)
    finally:
        await engine.dispose()


@celery_app.task(name="notifications.deliver", ignore_result=True)
def deliver_notification_task(delivery_id: int):
    asyncio.run(deliver(delivery_id))


@celery_app.task(name="notifications.recover_pending", ignore_result=True)
def recover_notification_deliveries():
    for delivery_id in asyncio.run(pending()):
        deliver_notification_task.delay(delivery_id)
