from typing import Literal

from pydantic import BaseModel

from app.services.grading import Grade


class UploadUrlIn(BaseModel):
    kind: Literal["pickup", "delivery", "weighbridge"]
    content_type: str = "image/jpeg"


class UploadUrlOut(BaseModel):
    path: str  # send this back as photo_path after uploading
    upload_url: str
    method: str = "PUT"


class LegIn(BaseModel):
    photo_path: str
    weight_kg: int


class GradeIn(BaseModel):
    photo_path: str | None = None  # a weighbridge photo to register and grade


class GradeOut(BaseModel):
    photo_id: str
    grade: Grade
    is_estimate: bool = True


class ConfirmIn(BaseModel):
    accept: bool
    final_weight_kg: int | None = None  # required when accepting (the weighbridge weight)
    reason: str = ""  # required when rejecting


class VerificationCallOut(BaseModel):
    call_id: str
    job_id: str
    farmer_id: str
    farmer_phone: str
