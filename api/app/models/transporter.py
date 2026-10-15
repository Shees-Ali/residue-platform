from datetime import datetime

from pydantic import BaseModel, Field


class TransporterOut(BaseModel):
    id: str
    user_uid: str | None = None
    display_name: str | None = None
    phone: str
    tier: int
    max_tonnes: float
    approved: bool
    approved_at: datetime | None
    lat: float
    lon: float


class ApproveIn(BaseModel):
    tier: int = Field(ge=1, le=3)  # the tier sets the largest job this transporter is offered
