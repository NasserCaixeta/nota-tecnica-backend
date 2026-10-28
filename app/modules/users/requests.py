from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountRequest(Base):
    __tablename__ = "account_requests"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('closure', 'identity_correction')", name="ck_account_request_kind"
        ),
        Index(
            "uq_pending_account_request",
            "user_id",
            "kind",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AccountRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=1000)


class AccountRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    kind: str
    reason: str
    status: str
    created_at: datetime


async def create_account_request(session, user, kind, reason):
    from app.modules.audit.service import append_audit

    await session.refresh(user, with_for_update=True)
    existing = await session.scalar(
        select(AccountRequest).where(
            AccountRequest.user_id == user.id,
            AccountRequest.kind == kind,
            AccountRequest.status == "pending",
        )
    )
    if existing:
        return existing
    request = AccountRequest(user_id=user.id, kind=kind, reason=reason.strip())
    if len(request.reason) < 10:
        raise HTTPException(422, "Descreva a solicitação em pelo menos dez caracteres.")
    session.add(request)
    await session.flush()
    await append_audit(
        session,
        actor_id=user.id,
        action="account_request.created",
        target_type="account_request",
        target_id=request.id,
        version=1,
        reason="participant_requested_administrative_review",
        metadata={"kind": kind, "user_id": user.id},
    )
    await session.commit()
    return request
