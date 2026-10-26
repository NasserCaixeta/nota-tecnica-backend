from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.validators import validate_cpf
from app.modules.users.models import ParticipationStatus, UserProfileType


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    cpf: str
    phone: str = Field(min_length=1, max_length=32)
    birth_date: date
    profile_type: UserProfileType
    zip_code: str = Field(min_length=1, max_length=16)
    street: str = Field(min_length=1, max_length=255)
    number: str = Field(min_length=1, max_length=32)
    neighborhood: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    complement: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("cpf")
    @classmethod
    def normalize_cpf(cls, value: str) -> str:
        return validate_cpf(value)

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.strip().upper()


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    cpf: str
    phone: str
    birth_date: date
    profile_type: UserProfileType
    zip_code: str
    street: str
    number: str
    neighborhood: str
    city: str
    state: str
    complement: str | None
    is_active: bool
    is_admin: bool
    participation_status: ParticipationStatus
    participation_version: int
    participation_reason: str | None
    capabilities: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"\S")
    phone: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"\S")
    city: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"\S")
    state: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def reject_null_updates(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Profile fields cannot be null")
        return self
