"""FA2: a visual grade of the delivered lot. An estimate; the weighbridge is authoritative."""
import os
from typing import Literal, Protocol

from fastapi import HTTPException
from pydantic import BaseModel, Field

GRADE_DISCLAIMER = "Visual estimate only; weighbridge confirmation required."
MOISTURE_BANDS = ("dry", "medium", "wet")
GEMINI_MODEL = os.getenv("GRADING_MODEL", "gemini-3.8-flash")

PROMPT = (
    "You grade photos of crop residue delivered to a biomass factory. From the photos only, give: "
    "the residue type (rice_straw, wheat_straw, cotton_stalk or sugarcane_trash), a moisture band "
    "(dry, medium or wet), contamination flags (short lowercase labels such as soil, plastic, "
    "stones, mold; empty if none) and your confidence from 0 to 1. This is an estimate."
)


class Grade(BaseModel):
    residue_type: str
    moisture_band: Literal["dry", "medium", "wet"]
    contamination_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    disclaimer: str = GRADE_DISCLAIMER


class Grader(Protocol):
    async def grade(self, images: list[bytes]) -> Grade: ...


class UnavailableGrader:
    """No Gemini key configured: grading is optional, so say so instead of failing oddly."""

    async def grade(self, images: list[bytes]) -> Grade:
        raise HTTPException(503, "Photo grading is not configured (set GEMINI_API_KEY)")


class GeminiGrader:
    # TODO(FA2): not exercised against the live API yet; verify with a real key and photos.
    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    async def grade(self, images: list[bytes]) -> Grade:
        from google.genai import types

        parts = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images]
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[*parts, PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=Grade
            ),
        )
        grade = Grade.model_validate_json(response.text)
        return grade.model_copy(update={"disclaimer": GRADE_DISCLAIMER})  # never model-written


_grader: Grader | None = None


def get_grader() -> Grader:
    """FastAPI dependency."""
    global _grader
    if _grader is None:
        key = os.getenv("GEMINI_API_KEY", "")
        _grader = GeminiGrader(key) if key and key != "changeme" else UnavailableGrader()
    return _grader
