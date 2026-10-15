from pydantic import BaseModel


class ResidueTypeOut(BaseModel):
    code: str
    label: str


class VillageOut(BaseModel):
    name: str
    district: str
