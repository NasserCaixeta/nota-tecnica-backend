import asyncio

from sqlalchemy import func, select

from app.modules.notifications.models import Notification
from app.modules.notifications.service import enqueue_notification
from tests.integration.test_admin_concurrency import prepare_users


async def test_same_notification_key_has_one_logical_result_under_concurrency(pg_engine):
    factory = await prepare_users(pg_engine)

    async def enqueue():
        async with factory() as session:
            notification = await enqueue_notification(
                session,
                recipient_id=3,
                kind="participation_updated",
                target_type="user",
                target_id=3,
                dedupe_key="same-decision",
            )
            await session.commit()
            return notification.id

    ids = await asyncio.gather(enqueue(), enqueue())
    assert ids[0] == ids[1]
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Notification)) == 1
