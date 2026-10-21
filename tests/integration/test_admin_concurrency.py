import asyncio
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.base import Base
from app.modules.admin.participation import review_participant, set_admin_access
from app.modules.audit.models import AuditEvent
from app.modules.users.models import ParticipationStatus, User, UserProfileType
from tests.test_auth_users import user_payload


async def prepare_users(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        for index, (email, cpf) in enumerate(
            [
                ("admin1@example.com", "52998224725"),
                ("admin2@example.com", "39053344705"),
                ("driver@example.com", "93541134780"),
            ]
        ):
            data = user_payload(email=email, cpf=cpf)
            data.pop("password")
            data["password_hash"] = "unused-test-password-hash"
            data["birth_date"] = date(1990, 1, 20)
            data["profile_type"] = UserProfileType.CUSTOMER
            session.add(
                User(
                    **data,
                    is_admin=index < 2,
                    participation_status=(
                        ParticipationStatus.APPROVED if index < 2 else ParticipationStatus.PENDING
                    ),
                )
            )
        await session.commit()
    return factory


async def test_concurrent_revocations_preserve_an_active_administrator(pg_engine):
    factory = await prepare_users(pg_engine)

    async def revoke_self(actor_id):
        async with factory() as session:
            actor = await session.get(User, actor_id)
            try:
                await set_admin_access(
                    session,
                    actor=actor,
                    user_id=actor_id,
                    enabled=False,
                    reason="Concurrent removal",
                )
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    results = await asyncio.gather(revoke_self(1), revoke_self(2))
    assert sorted(results) == [200, 409]
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            )
            == 1
        )


async def test_concurrent_reviews_only_apply_one_version(pg_engine):
    factory = await prepare_users(pg_engine)

    async def review(actor_id, decision):
        async with factory() as session:
            actor = await session.get(User, actor_id)
            try:
                await review_participant(
                    session,
                    actor=actor,
                    user_id=3,
                    decision=decision,
                    expected_version=1,
                    reason="Concurrent review",
                )
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    results = await asyncio.gather(
        review(1, ParticipationStatus.APPROVED), review(2, ParticipationStatus.REJECTED)
    )
    assert sorted(results) == [200, 409]
    async with factory() as session:
        user = await session.get(User, 3)
        assert user.participation_version == 2
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
