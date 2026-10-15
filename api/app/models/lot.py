from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.validation import Phone, text

QUANTITY_HELP = "Quantity must be more than 0 and at most 100 tonnes"


def check_quantity(v: float) -> float:
    """More than 0, at most 100 tonnes, at most 2 decimals (the form and the admin entry)."""
    if isinstance(v, bool) or not isinstance(v, int | float) or not 0 < v <= 100:
        raise ValueError(QUANTITY_HELP)
    if Decimal(str(v)).as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError("Quantity can have at most 2 decimals")
    return v


class LotReadback(BaseModel):
    """Everything the agent needs to read a saved lot back to the farmer."""

    lot_id: str
    residue_type: str
    residue_label: str
    quantity_tonnes: float
    village: str
    district: str
    place_match: Literal["exact", "fuzzy", "district"]
    pickup_from: datetime
    pickup_to: datetime
    pickup_text: str


class LotOut(BaseModel):
    id: str
    farmer_id: str
    farmer_name: str | None = None
    farmer_phone: str | None = None
    residue_type: str
    residue_label: str | None = None
    quantity_tonnes: float
    village: str | None = None
    district: str | None = None
    place_match: str | None = None  # exact | fuzzy | district (the district centre was used)
    lat: float
    lon: float
    status: str
    factory_name: str | None = None  # the factory the lot was matched to
    quoted_price_per_tonne: int | None = None
    farmer_share_bps: int | None = None
    est_farmer_payout: int | None = None  # paisa, an estimate until the weighbridge
    pickup_from: datetime | None
    pickup_to: datetime | None
    job_id: str | None = None
    job_state: str | None = None
    created_at: datetime


class AdminLotIn(BaseModel):
    """Manual lot entry by an admin on behalf of a farmer (same validation as the agent)."""

    farmer_phone: Phone
    farmer_name: text(0, 80) | None = None  # used only when the farmer is new
    residue_type: text(1, 80)
    quantity_tonnes: float
    pickup_date: text(1, 10)
    pickup_part: text(1, 80)
    village: text(1, 80)
    district: text(1, 80)

    _quantity = field_validator("quantity_tonnes")(check_quantity)


class MineLotIn(BaseModel):
    """A farmer reporting their own residue on the web. Who they are comes from the login."""

    residue_type: text(1, 80)
    quantity_tonnes: float
    pickup_date: text(1, 10)  # YYYY-MM-DD
    pickup_part: text(1, 80)  # morning | afternoon | evening
    village: text(1, 80)
    district: text(1, 80)

    _quantity = field_validator("quantity_tonnes")(check_quantity)


class RankingEntry(BaseModel):
    factory_id: str
    factory_name: str
    rank: int
    score: float
    distance_km: float
    price_per_tonne: int
    chosen: bool
    override_reason: str | None = None


class OverrideIn(BaseModel):
    factory_id: text(1, 36)
    reason: text(3, 500)


class LotEditIn(BaseModel):
    """Admin: change a lot that is not funded yet. Same rules as reporting it."""

    model_config = ConfigDict(extra="forbid")

    quantity_tonnes: float | None = None
    pickup_date: text(1, 10) | None = None  # YYYY-MM-DD
    pickup_part: text(1, 80) | None = None
    village: text(1, 80) | None = None
    district: text(1, 80) | None = None

    @field_validator("quantity_tonnes")
    @classmethod
    def _quantity(cls, v):
        return v if v is None else check_quantity(v)


class LotEditOut(LotOut):
    override_dropped: bool = False  # a manual factory choice was replaced by the new ranking
