from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.models import UserProfileType


def normalize_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class UserCreate(BaseModel):
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
        normalized = normalize_digits(value)
        if len(normalized) != 11:
            raise ValueError("CPF must contain 11 digits")
        return normalized

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
    created_at: datetime
    updated_at: datetime
