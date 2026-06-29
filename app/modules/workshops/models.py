from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.vehicles.models import VerificationStatus


class WorkshopSource(StrEnum):
    USER_SUBMITTED = "user_submitted"
    OWNER_CLAIMED = "owner_claimed"


class WorkshopUserRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(16), nullable=False)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    neighborhood: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    complement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    specialties: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source: Mapped[WorkshopSource] = mapped_column(
        Enum(WorkshopSource, native_enum=False),
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False),
        nullable=False,
    )
    submitted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user_links: Mapped[list["WorkshopUser"]] = relationship(
        back_populates="workshop",
        cascade="all, delete-orphan",
    )


class WorkshopUser(Base):
    __tablename__ = "workshop_users"
    __table_args__ = (UniqueConstraint("workshop_id", "user_id", name="uq_workshop_users_link"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[WorkshopUserRole] = mapped_column(
        Enum(WorkshopUserRole, native_enum=False),
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    workshop: Mapped[Workshop] = relationship(back_populates="user_links")
