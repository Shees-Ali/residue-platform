from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.validation import text

PRICE_HELP = "Price must be between PKR 1 and PKR 1,000,000"
STOCK_HELP = "Stock must be a whole number from 0 to 1,000,000"
QUANTITY_HELP = "Quantity must be a whole number between 1 and 1000"
Category = Literal["Clean Energy", "Farming & Garden", "Building Materials", "Home & Living"]


def _name(v: str) -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Product name must be at least 2 characters")
    if len(v) > 120:
        raise ValueError("Product name must be at most 120 characters")
    return v


def _price(v: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not 100 <= v <= 100_000_000:
        raise ValueError(PRICE_HELP)  # paisa: PKR 1 to PKR 1,000,000
    return v


def _stock(v: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 1_000_000:
        raise ValueError(STOCK_HELP)
    return v


class ProductIn(BaseModel):
    name: str
    unit_price: int  # paisa
    stock: int
    category: Category
    unit: text(2, 40)  # for example "per 25 kg bag"
    description: text(0, 500) = ""

    _name = field_validator("name")(_name)
    _price = field_validator("unit_price", mode="before")(_price)
    _stock = field_validator("stock", mode="before")(_stock)


class ProductPatch(BaseModel):
    name: str | None = None
    unit_price: int | None = None
    stock: int | None = None
    category: Category | None = None
    unit: text(2, 40) | None = None
    description: text(0, 500) | None = None
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        return None if v is None else _name(v)

    @field_validator("unit_price", mode="before")
    @classmethod
    def _p(cls, v):
        return None if v is None else _price(v)

    @field_validator("stock", mode="before")
    @classmethod
    def _s(cls, v):
        return None if v is None else _stock(v)


class ProductOut(BaseModel):
    id: str
    factory_id: str
    factory_name: str
    name: str
    unit_price: int
    stock: int
    category: str
    unit: str
    description: str
    active: bool


class OrderIn(BaseModel):
    product_id: str
    quantity: int

    @field_validator("quantity", mode="before")
    @classmethod
    def _quantity(cls, v):
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1000:
            raise ValueError(QUANTITY_HELP)
        return v


class SplitLine(BaseModel):
    party: str
    share_bps: int
    amount: int


class OrderOut(BaseModel):
    id: str
    product_id: str
    product_name: str | None = None
    quantity: int
    total: int
    status: str
    created_at: datetime | None = None
    splits: list[SplitLine]
    shares_total_bps: int
    amounts_total: int
