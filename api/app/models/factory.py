from pydantic import BaseModel


class Factory(BaseModel):
    id: str
    accepted_residues: list[str]
    lat: float
    lon: float
    price_per_tonne_cents: int


class LotRequest(BaseModel):
    residue_type: str
    lat: float
    lon: float
    quantity_tonnes: float
