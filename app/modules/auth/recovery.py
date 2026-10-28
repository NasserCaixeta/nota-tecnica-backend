import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit.service import append_audit
from app.modules.auth.models import PasswordRecovery
from app.modules.auth.security import hash_password
from app.modules.notifications.service import enqueue_notification
from app.modules.users.models import User

NEUTRAL_MESSAGE = (
    "Se houver uma conta elegível para este e-mail, "
    "as instruções de recuperação serão encaminhadas."
)


def recovery_token(nonce: str):
    key = get_settings().recovery_secret_key.get_secret_value()
    if len(key) < 32:
        raise HTTPException(503, "Recuperação de acesso temporariamente indisponível.")
    return nonce + "." + hmac.new(key.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def request_recovery(session: AsyncSession, email: str):
    recovery_token("configuration-check")
    user = await session.scalar(
        select(User).where(User.email == email.casefold()).with_for_update()
    )
    if user is None or not user.is_active:
        return
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordRecovery)
        .where(
            PasswordRecovery.user_id == user.id,
            PasswordRecovery.consumed_at.is_(None),
            PasswordRecovery.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    nonce = secrets.token_urlsafe(32)
    token = recovery_token(nonce)
    recovery = PasswordRecovery(
        user_id=user.id,
        nonce=nonce,
        token_hash=hash_token(token),
        auth_version_at_issue=user.auth_version,
        created_at=now,
        expires_at=now + timedelta(minutes=60),
    )
    session.add(recovery)
    await session.flush()
    await enqueue_notification(
        session,
        recipient_id=user.id,
        kind="password_recovery",
        target_type="password_recovery",
        target_id=recovery.id,
        dedupe_key=f"password-recovery:{recovery.id}",
    )
    await append_audit(
        session,
        actor_id=None,
        action="auth.recovery_requested",
        target_type="password_recovery",
        target_id=recovery.id,
        version=1,
        reason="self_service_request",
        metadata={"user_id": user.id},
    )
    await session.commit()


async def reset_password(session: AsyncSession, token: str, password: str):
    initial = await session.scalar(
        select(PasswordRecovery).where(PasswordRecovery.token_hash == hash_token(token))
    )
    if initial is None:
        raise HTTPException(400, "Link de recuperação inválido ou expirado.")
    # Same lock order as request_recovery: user first, recovery second.
    user = await session.scalar(
        select(User)
        .where(User.id == initial.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    recovery = await session.scalar(
        select(PasswordRecovery)
        .where(PasswordRecovery.id == initial.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if (
        user is None
        or not user.is_active
        or recovery.consumed_at is not None
        or recovery.revoked_at is not None
        or utc(recovery.expires_at) <= now
        or recovery.auth_version_at_issue != user.auth_version
        or not hmac.compare_digest(token, recovery_token(recovery.nonce))
    ):
        raise HTTPException(400, "Link de recuperação inválido ou expirado.")
    user.password_hash = hash_password(password)
    user.auth_version += 1
    recovery.consumed_at = now
    await session.execute(
        update(PasswordRecovery)
        .where(
            PasswordRecovery.user_id == user.id,
            PasswordRecovery.id != recovery.id,
            PasswordRecovery.consumed_at.is_(None),
            PasswordRecovery.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await append_audit(
        session,
        actor_id=user.id,
        action="auth.password_reset",
        target_type="user",
        target_id=user.id,
        version=user.auth_version,
        reason="valid_single_use_recovery",
    )
    await session.commit()


async def render_recovery_email(session, recovery_id, now):
    from app.modules.notifications.delivery import ObsoleteMessage

    recovery = await session.get(PasswordRecovery, recovery_id, populate_existing=True)
    if (
        recovery is None
        or recovery.consumed_at is not None
        or recovery.revoked_at is not None
        or utc(recovery.expires_at) <= now
    ):
        raise ObsoleteMessage()
    user = await session.get(User, recovery.user_id, populate_existing=True)
    if user is None or not user.is_active or user.auth_version != recovery.auth_version_at_issue:
        raise ObsoleteMessage()
    token = recovery_token(recovery.nonce)
    if hash_token(token) != recovery.token_hash:
        raise ObsoleteMessage()
    link = f"{get_settings().frontend_url.rstrip('/')}/redefinir-senha#{token}"
    return (
        user.email,
        "Recuperação de acesso — Nota Técnica",
        (
            "Use o link pessoal para escolher uma nova senha:\n\n"
            f"{link}\n\nO link expira em 60 minutos e funciona uma única vez. "
            "Se você não solicitou a recuperação, ignore esta mensagem."
        ),
    )
