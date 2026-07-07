from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.validators import validate_cnpj
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.models import WorkshopSource, WorkshopUserRole


class WorkshopCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str = Field(min_length=1, max_length=255)
    cnpj: str
    phone: str = Field(min_length=1, max_length=32)
    email: EmailStr
    zip_code: str = Field(min_length=1, max_length=16)
    street: str = Field(min_length=1, max_length=255)
    number: str = Field(min_length=1, max_length=32)
    neighborhood: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    complement: str | None = Field(default=None, max_length=120)
    specialties: list[str] = Field(min_length=1)
    source: WorkshopSource

    @field_validator("cnpj")
    @classmethod
    def normalize_cnpj(cls, value: str) -> str:
        return validate_cnpj(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.strip().upper()


class WorkshopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    legal_name: str
    trade_name: str
    cnpj: str
    phone: str
    email: EmailStr
    zip_code: str
    street: str
    number: str
    neighborhood: str
    city: str
    state: str
    complement: str | None
    specialties: list[str]
    source: WorkshopSource
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime


class ManagedWorkshopRead(WorkshopRead):
    role: WorkshopUserRole
