from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    body: str
    target_type: str
    target_id: int
    created_at: datetime
    read_at: datetime | None
    link: str | None = None
