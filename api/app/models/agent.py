"""Request bodies for /api/agent/*.

Deliberately NO farmer id: identity comes from the call record.
"""
from pydantic import BaseModel


class CreateLotIn(BaseModel):
    call_id: str
    residue_type: str
    quantity_tonnes: float
    pickup_window: str
    village: str
    district: str


class GetQuoteIn(BaseModel):
    call_id: str
    lot_id: str


class EscalateIn(BaseModel):
    call_id: str
    summary: str
    transcript: str = ""


class RecordConfirmationIn(BaseModel):
    call_id: str
    job_id: str
    confirmed: bool
    note: str = ""
