from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
