"""Request bodies for /api/agent/*.

Deliberately NO farmer id: identity comes from the call record.
Fields the model fills are plain strings/numbers: the API validates them and answers with a
recoverable 422 {error, message, valid} so the agent can ask the farmer again.
"""
from pydantic import BaseModel


class CreateLotIn(BaseModel):
    call_id: str
    residue_type: str  # a residue_types.code, e.g. rice_straw
    quantity_tonnes: float
    pickup_date: str  # ISO date, YYYY-MM-DD
    pickup_part: str  # morning | afternoon | evening
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
