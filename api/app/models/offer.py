from datetime import datetime

from pydantic import BaseModel


class Offer(BaseModel):
    id: str
    job_id: str
    transporter_id: str
    expires_at: datetime
    status: str = "pending"  # pending | accepted | expired | withdrawn
