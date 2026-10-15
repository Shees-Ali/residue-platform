from datetime import datetime

from pydantic import BaseModel


class EscalationOut(BaseModel):
    id: str
    call_id: str | None = None
    job_id: str | None = None
    summary: str
    transcript: str
    status: str
    farmer_phone: str | None = None
    created_at: datetime
