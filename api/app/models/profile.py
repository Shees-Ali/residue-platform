"""Edit my details (and the admin's edit of anyone). Rules: memory/validation-rules.md,
"Edit my details, and admin edits". Every field is optional; at least one must be sent."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.me import PRICE_HELP, Residue
from app.validation import DistinctList, Phone, text

Residues = Annotated[list[Residue], Field(min_length=1, max_length=10), DistinctList]
MAX_LOAD_HELP = "Max load must be more than 0 and at most 100 tonnes"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unknown field is refused, not ignored


class FactoryEditIn(_Strict):
    name: text(2, 120) | None = None
    price_per_tonne: int | None = None  # paisa
    residues: Residues | None = None

    @field_validator("price_per_tonne", mode="before")
    @classmethod
    def _price(cls, v):
        if v is None:
            return v
        if isinstance(v, bool) or not isinstance(v, int) or not 100 <= v <= 100_000_000:
            raise ValueError(PRICE_HELP)
        return v


class TransporterAdminEditIn(_Strict):
    """Only an admin may send this."""

    tier: int | None = None
    max_tonnes: float | None = None

    @field_validator("tier", mode="before")
    @classmethod
    def _tier(cls, v):
        if v is None:
            return v
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 3:
            raise ValueError("Tier must be 1, 2 or 3")
        return v

    @field_validator("max_tonnes", mode="before")
    @classmethod
    def _max(cls, v):
        if v is None:
            return v
        if isinstance(v, bool) or not isinstance(v, int | float) or not 0 < v <= 100:
            raise ValueError(MAX_LOAD_HELP)
        return v


class ProfileEditIn(_Strict):
    display_name: text(2, 80) | None = None
    phone: Phone | None = None
    district: text(2, 80) | None = None
    village: text(2, 80) | None = None
    factory: FactoryEditIn | None = None
    transporter: TransporterAdminEditIn | None = None


class FactoryProfileOut(BaseModel):
    name: str
    price_per_tonne: int
    residues: list[str]


class TransporterProfileOut(BaseModel):
    tier: int
    max_tonnes: float
    approved: bool


class ProfileOut(BaseModel):
    uid: str
    email: str | None
    role: str
    status: str
    display_name: str
    phone: str | None
    district: str | None = None
    village: str | None = None
    factory: FactoryProfileOut | None = None
    transporter: TransporterProfileOut | None = None
