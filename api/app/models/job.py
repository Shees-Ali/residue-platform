from datetime import datetime

from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    lot_id: str
    factory_id: str
    factory_name: str | None = None
    transporter_id: str | None = None
    state: str
    residue_type: str | None = None
    quantity_tonnes: float | None = None
    village: str | None = None
    quoted_price_per_tonne: int
    farmer_share_bps: int
    est_weight_kg: int
    final_weight_kg: int | None = None
    rejection_reason: str | None = None
    offers_exhausted: bool = False
    funded_at: datetime | None = None
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    confirmed_at: datetime | None = None
    verified_at: datetime | None = None
    settled_at: datetime | None = None
    created_at: datetime
