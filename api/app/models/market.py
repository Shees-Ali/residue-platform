from pydantic import BaseModel, Field


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    unit_price: int = Field(gt=0)  # minor units
    stock: int = Field(ge=0)


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit_price: int | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    active: bool | None = None


class ProductOut(BaseModel):
    id: str
    factory_id: str
    factory_name: str
    name: str
    unit_price: int
    stock: int
    active: bool


class OrderIn(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class SplitLine(BaseModel):
    party: str
    share_bps: int
    amount: int


class OrderOut(BaseModel):
    id: str
    product_id: str
    quantity: int
    total: int
    status: str
    splits: list[SplitLine]
    shares_total_bps: int
    amounts_total: int
