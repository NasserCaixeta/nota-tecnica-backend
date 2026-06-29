from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserProfileType(StrEnum):
    CUSTOMER = "customer"
    WORKSHOP_OWNER = "workshop_owner"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    profile_type: Mapped[UserProfileType] = mapped_column(
        Enum(UserProfileType, native_enum=False),
        nullable=False,
    )
    zip_code: Mapped[str] = mapped_column(String(16), nullable=False)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    neighborhood: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    complement: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
