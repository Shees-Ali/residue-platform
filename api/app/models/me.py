from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.validation import DistinctList, Phone, text

PRICE_HELP = "Price must be between PKR 1 and PKR 1,000,000 per tonne"
Residue = Annotated[str, StringConstraints(pattern=r"^[a-z_]{2,40}$")]


class FactoryProfileIn(BaseModel):
    name: text(2, 120)
    price_per_tonne: int  # paisa
    residues: Annotated[list[Residue], Field(min_length=1, max_length=10), DistinctList]

    @field_validator("price_per_tonne")
    @classmethod
    def _price(cls, v: int) -> int:
        if not 100 <= v <= 100_000_000:
            raise ValueError(PRICE_HELP)
        return v


class RegisterIn(BaseModel):
    """Self-signup. `admin` is not a choice: it is granted only by BOOTSTRAP_ADMIN_EMAILS.

    Which of the optional fields a role needs is checked in `services.registration`, so every
    missing field is reported at once. Rules: memory/validation-rules.md.
    """

    role: Literal["farmer", "buyer", "transporter", "factory"]
    display_name: text(2, 80)
    phone: Phone | None = None  # transporters; farmers use the verified phone on their token
    village: text(2, 80) | None = None  # transporters and factories: where they are based
    district: text(2, 80) | None = None
    factory: FactoryProfileIn | None = None  # factories


class MeOut(BaseModel):
    uid: str
    email: str | None
    role: str
    status: str  # active | pending | suspended
    display_name: str
    phone: str | None
    farmer_linked: bool | None = None  # farmers: is a phone-verified farmer record attached?


class ApproveIn(BaseModel):
    tier: int = Field(default=1, ge=1, le=3)  # transporters: the largest job they are offered

    @field_validator("tier", mode="before")
    @classmethod
    def _tier(cls, v):
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 3:
            raise ValueError("Tier must be 1, 2 or 3")
        return v


class UserOut(BaseModel):
    uid: str
    email: str | None
    role: str
    status: str
    display_name: str
    phone: str | None
    created_at: datetime
    details: dict[str, Any] = {}  # what they signed up with (factory name and price, base, ...)
