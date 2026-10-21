from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.models import ParticipationStatus


class ParticipantReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ParticipationStatus
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class AdminAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")
