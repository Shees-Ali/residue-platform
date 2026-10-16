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


class CheckStatusIn(BaseModel):
    call_id: str = Field(min_length=1, max_length=64)


class RequestStatusOut(BaseModel):
    """One of the caller's requests (F5). Unverified callers get only the first six fields."""

    lot_id: str
    residue_label: str | None = None
    reported_on: str  # YYYY-MM-DD, Pakistan time
    stage: str
    status_text: str
    details_withheld: bool | None = None  # true on the /phone page: no places, factory or money
    quantity_tonnes: float | None = None
    village: str | None = None
    district: str | None = None
    pickup_text: str | None = None
    factory_name: str | None = None
    est_farmer_amount_rupees: float | None = None
    final_weight_kg: int | None = None
    farmer_amount_rupees: float | None = None
    rejection_reason: str | None = None


class CheckStatusOut(BaseModel):
    requests: list[RequestStatusOut]


class RecordConfirmationIn(BaseModel):
    call_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)
    confirmed: bool
    note: text(0, 1000) = ""
