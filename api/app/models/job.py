from datetime import datetime

from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: str
    kind: str  # pickup | delivery | weighbridge
    weight_kg: int | None = None
    url: str  # where the browser can load it
    created_at: datetime


class JobOut(BaseModel):
    id: str
    lot_id: str
    factory_id: str
    factory_name: str | None = None
    transporter_id: str | None = None
    transporter_name: str | None = None
    state: str
    residue_type: str | None = None
    quantity_tonnes: float | None = None
    village: str | None = None
    district: str | None = None
    # where to collect and where to deliver (for the map and the transporter)
    pickup_lat: float | None = None
    pickup_lon: float | None = None
    factory_lat: float | None = None
    factory_lon: float | None = None
    # the farmer's contact: only the admin and the transporter who accepted the job see it
    farmer_name: str | None = None
    farmer_phone: str | None = None
    quoted_price_per_tonne: int
    farmer_share_bps: int
    est_weight_kg: int
    final_weight_kg: int | None = None
    # paisa. The escrow is what the factory funds at the estimated weight; the payouts follow the
    # final weight once the factory has confirmed it, the estimate before that.
    escrow_amount: int = 0
    est_farmer_payout: int = 0
    est_transporter_payout: int = 0
    rejection_reason: str | None = None
    photos: list[PhotoOut] = []
    offers_exhausted: bool = False
    funded_at: datetime | None = None
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    confirmed_at: datetime | None = None
    verified_at: datetime | None = None
    settled_at: datetime | None = None
    created_at: datetime


class JobOfferOut(BaseModel):
    """One step of the offer ladder, as the admin sees it."""

    id: str
    sequence: int
    transporter_id: str
    transporter_name: str | None = None
    transporter_phone: str | None = None
    status: str  # pending | accepted | expired | withdrawn
    expires_at: datetime
    payout_amount: int
