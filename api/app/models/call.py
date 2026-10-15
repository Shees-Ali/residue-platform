from typing import Literal

from pydantic import BaseModel, Field


class CallStartIn(BaseModel):
    """Sent by the voice transport layer (not the model) when a call connects."""

    twilio_call_sid: str = Field(min_length=1, max_length=64)
    caller_phone: str = Field(pattern=r"^\+\d{8,15}$")
    kind: Literal["intake", "verification"] = "intake"


class CallStartOut(BaseModel):
    call_id: str
    farmer_known: bool  # the farmer already has a name on file


class CallEndIn(BaseModel):
    status: Literal["completed", "abandoned", "failed"] = "completed"
    transcript: str = Field(default="", max_length=50000)
    summary: str = Field(default="", max_length=2000)


class CallEndOut(BaseModel):
    call_id: str
    status: str
