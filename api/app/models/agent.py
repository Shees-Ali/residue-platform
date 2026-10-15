"""Request bodies for /api/agent/*.

Deliberately NO farmer id: identity comes from the call record.
Fields the model fills are plain strings/numbers: the API validates them and answers with a
recoverable 422 {error, message, valid} so the agent can ask the farmer again.
"""
from pydantic import BaseModel, Field

from app.validation import text


class CreateLotIn(BaseModel):
    call_id: str = Field(max_length=64)
    residue_type: str = Field(max_length=40)  # a residue_types.code, e.g. rice_straw
    quantity_tonnes: float
    pickup_date: str = Field(max_length=10)  # ISO date, YYYY-MM-DD
    pickup_part: str = Field(max_length=20)  # morning | afternoon | evening
    village: str = Field(max_length=80)
    district: str = Field(max_length=80)


class GetQuoteIn(BaseModel):
    call_id: str = Field(max_length=64)
    lot_id: str = Field(max_length=64)


class EscalateIn(BaseModel):
    call_id: str = Field(max_length=64)
    summary: text(1, 2000)
    transcript: text(0, 50000) = ""


class RecordConfirmationIn(BaseModel):
    call_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)
    confirmed: bool
    note: text(0, 1000) = ""
