from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.validation import Phone, text


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
    residue_type: str
    quantity_tonnes: float
    lat: float
    lon: float
    status: str
    pickup_from: datetime | None
    pickup_to: datetime | None
    job_id: str | None = None
    job_state: str | None = None
    created_at: datetime


class AdminLotIn(BaseModel):
    """Manual lot entry by an admin on behalf of a farmer (same validation as the agent)."""

    farmer_phone: Phone
    residue_type: text(1, 80)
    quantity_tonnes: float
    pickup_date: text(1, 10)
    pickup_part: text(1, 80)
    village: text(1, 80)
    district: text(1, 80)


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
