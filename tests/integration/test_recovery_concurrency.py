import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import get_settings
from app.modules.audit.models import AuditEvent
from app.modules.auth.models import PasswordRecovery
from app.modules.auth.recovery import hash_token, recovery_token, reset_password
from app.modules.users.models import User
from tests.integration.test_admin_concurrency import prepare_users


async def test_same_recovery_token_can_change_password_only_once(pg_engine, monkeypatch):
    monkeypatch.setenv("RECOVERY_SECRET_KEY", "recovery-key-separate-with-at-least-32-characters")
    get_settings.cache_clear()
    factory = await prepare_users(pg_engine)
    token = recovery_token("synthetic-one-use-nonce")
    async with factory() as session:
        session.add(
            PasswordRecovery(
                user_id=3,
                nonce="synthetic-one-use-nonce",
                token_hash=hash_token(token),
                auth_version_at_issue=1,
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=60),
            )
        )
        await session.commit()

    async def reset():
        async with factory() as session:
            try:
                await reset_password(session, token, "new-strong-password")
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(reset(), reset())) == [200, 400]
    async with factory() as session:
        assert (await session.get(User, 3)).auth_version == 2
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "auth.password_reset")
            )
            == 1
        )
    get_settings.cache_clear()
