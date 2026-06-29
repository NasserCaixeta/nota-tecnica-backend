from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.vehicles.models import VehicleRelationshipType, VerificationStatus


class VehicleCreate(BaseModel):
    plate: str
    brand: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    model_year: int = Field(ge=1900, le=2100)
    color: str = Field(min_length=1, max_length=60)
    vehicle_type: str = Field(min_length=1, max_length=60)
    chassis: str = Field(min_length=1, max_length=32)
    renavam: str = Field(min_length=1, max_length=32)
    fuel_type: str = Field(min_length=1, max_length=60)
    engine: str = Field(min_length=1, max_length=120)
    transmission: str = Field(min_length=1, max_length=60)

    @field_validator("plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return "".join(character for character in value if character.isalnum()).upper()


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    brand: str
    model: str
    model_year: int
    color: str
    vehicle_type: str
    chassis: str
    renavam: str
    fuel_type: str
    engine: str
    transmission: str
    relationship_type: VehicleRelationshipType
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime
