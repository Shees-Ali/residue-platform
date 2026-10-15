from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.grading import Grade

WEIGHT_HELP = "Weight must be a whole number of kilograms between 1 and 100,000"
LOCATION_HELP = "Allow location access to record this step"


class UploadUrlIn(BaseModel):
    kind: Literal["pickup", "delivery", "weighbridge"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"


class UploadUrlOut(BaseModel):
    path: str  # send this back as photo_path after uploading
    upload_url: str
    method: str = "PUT"


def _check_lat(v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not -90 <= v <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    return float(v)


def _check_lon(v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not -180 <= v <= 180:
        raise ValueError("Longitude must be between -180 and 180")
    return float(v)


class Position(BaseModel):
    """A reading from the phone. Accuracy is how many metres it might be off by."""

    lat: float
    lon: float
    accuracy_m: float | None = None

    _lat = field_validator("lat")(_check_lat)
    _lon = field_validator("lon")(_check_lon)

    @field_validator("accuracy_m")
    @classmethod
    def _accuracy(cls, v: float | None) -> float | None:
        if v is not None and not 0 <= v <= 100_000:
            raise ValueError("Accuracy must be between 0 and 100,000 metres")
        return v


class LegIn(Position):
    """Record a pickup or delivery: the photo, the weight and where the transporter is."""

    photo_path: str = Field(max_length=300)
    weight_kg: int

    @field_validator("photo_path")
    @classmethod
    def _photo(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Add a photo (JPEG, PNG or WebP, up to 5 MB)")
        return v.strip()

    @field_validator("weight_kg", mode="before")
    @classmethod
    def _weight(cls, v):
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 100_000:
            raise ValueError(WEIGHT_HELP)
        return v


class PingIn(Position):
    """A position sent while the job is in progress."""


class PingOut(BaseModel):
    recorded: bool  # False when it came too soon after the last one and was dropped


class GradeIn(BaseModel):
    # a weighbridge photo to register and grade
    photo_path: str | None = Field(default=None, max_length=300)


class GradeOut(BaseModel):
    photo_id: str
    grade: Grade
    is_estimate: bool = True


class ConfirmIn(BaseModel):
    accept: bool
    final_weight_kg: int | None = None  # required when accepting (the weighbridge weight)
    reason: str = Field(default="", max_length=500)  # required when rejecting


class VerifyIn(BaseModel):
    """The farmer's answer on the web: yes, pay out, or no, I dispute the weight or payment."""

    confirmed: bool
    note: str = ""

    @field_validator("note")
    @classmethod
    def _note(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 1000:
            raise ValueError("Note must be at most 1000 characters")
        return v


class VerifyOut(BaseModel):
    job_id: str
    state: str  # settled | disputed
    farmer_amount: int | None = None  # paisa released to the farmer, when confirmed


class VerificationCallOut(BaseModel):
    call_id: str
    job_id: str
    farmer_id: str
    farmer_phone: str | None = None
