from pydantic import BaseModel


class Grade(BaseModel):
    residue_type: str
    moisture_band: str
    contamination_flags: list[str]
    confidence: float
    disclaimer: str = "Visual estimate only; weighbridge confirmation required."


async def grade_photos(photo_uris: list[str]) -> Grade:
    """Grade lot photos with Gemini vision."""
    # TODO(FA2): call Gemini with a structured-output schema.
    raise NotImplementedError
