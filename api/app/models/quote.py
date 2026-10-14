from pydantic import BaseModel


class QuoteOut(BaseModel):
    """What the agent says to the farmer. Rupee fields are for speaking, paisa fields are exact."""

    lot_id: str
    price_per_tonne: int
    price_per_tonne_rupees: float
    farmer_share_bps: int
    farmer_share_percent: float
    farmer_per_tonne_rupees: float
    est_weight_kg: int
    est_total: int
    est_farmer_amount: int
    est_farmer_amount_rupees: float
    payment_timing: str
