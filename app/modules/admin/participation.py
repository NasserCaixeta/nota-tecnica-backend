from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
from app.modules.users.models import ParticipationStatus, User


async def lock_administration(session: AsyncSession) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(730041)"))


async def require_another_admin(session: AsyncSession, user_id: int) -> None:
    count = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.id != user_id,
            User.is_admin.is_(True),
            User.is_active.is_(True),
            User.participation_status == ParticipationStatus.APPROVED,
        )
    )
    if not count:
        raise HTTPException(
            status_code=409, detail="The last active administrator must be preserved"
        )


async def require_current_authority(session: AsyncSession, actor: User) -> None:
    await session.refresh(actor)
    if (
        not actor.is_admin
        or not actor.is_active
        or (actor.participation_status != ParticipationStatus.APPROVED)
    ):
        raise HTTPException(status_code=403, detail="Administrative access is required")


async def review_participant(
    session: AsyncSession,
    *,
    actor: User,
    user_id: int,
    decision: ParticipationStatus,
    expected_version: int,
    reason: str,
) -> User:
    await lock_administration(session)
    await require_current_authority(session, actor)
    if actor.id == user_id:
        raise HTTPException(status_code=409, detail="Administrators cannot review themselves")
    user = await session.get(User, user_id, populate_existing=True)
    if user is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if decision == ParticipationStatus.PENDING:
        raise HTTPException(status_code=422, detail="Choose approved, rejected or suspended")
    if user.is_admin and decision != ParticipationStatus.APPROVED:
        await require_another_admin(session, user_id)
    result = await session.execute(
        update(User)
        .where(
            User.id == user_id,
            User.participation_version == expected_version,
        )
        .values(
            participation_status=decision,
            participation_reason=reason,
            participation_version=expected_version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(
            status_code=409, detail="Participant review has changed; refresh the request"
        )
    await append_audit(
        session,
        actor_id=actor.id,
        action="participant.review",
        target_type="user",
        target_id=user_id,
        version=expected_version + 1,
        reason=reason,
        metadata={"decision": decision.value},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def set_admin_access(
    session: AsyncSession,
    *,
    actor: User,
    user_id: int,
    enabled: bool,
    reason: str,
) -> User:
    await lock_administration(session)
    await require_current_authority(session, actor)
    user = await session.get(User, user_id, populate_existing=True)
    if user is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    if enabled and (
        not user.is_active or user.participation_status != ParticipationStatus.APPROVED
    ):
        raise HTTPException(
            status_code=409, detail="Only active approved participants can administer"
        )
    if not enabled and user.is_admin:
        await require_another_admin(session, user_id)
    user.is_admin = enabled
    await append_audit(
        session,
        actor_id=actor.id,
        action="admin_access.update",
        target_type="user",
        target_id=user_id,
        reason=reason,
        metadata={"enabled": enabled},
    )
    await session.commit()
    await session.refresh(user)
    return user
