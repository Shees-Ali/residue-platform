from datetime import datetime

from pydantic import BaseModel


class OfferOut(BaseModel):
    """What a transporter sees: where, how much, how long they have."""

    id: str
    job_id: str
    status: str
    expires_at: datetime
    payout_amount: int  # estimate; the final payout follows the weighbridge weight
    est_weight_kg: int
    residue_type: str
    village: str | None
    pickup_lat: float
    pickup_lon: float
    factory_name: str
    factory_lat: float
    factory_lon: float


class TickIn(BaseModel):
    force: bool = False  # demo fast-forward: expire every pending offer now (admin only)


class TickOut(BaseModel):
    expired: int
    reoffered: int
    exhausted: int
    dispatched: int = 0  # funded jobs that had no offer yet and got their first one
