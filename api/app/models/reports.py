from datetime import datetime

from pydantic import BaseModel


class LedgerEntryOut(BaseModel):
    id: str
    job_id: str | None
    order_id: str | None
    kind: str
    amount: int
    created_at: datetime


class LedgerCheckOut(BaseModel):
    balanced: bool  # every finished job and every order reconciles
    jobs_checked: int
    orders_checked: int
    unbalanced_jobs: list[str]
    unbalanced_orders: list[str]
    held_in_escrow: int  # money funded for jobs that are not finished yet
    totals: dict[str, int]


class PayoutOut(BaseModel):
    job_id: str
    state: str
    status: str  # pending until the factory confirms, then released
    amount: int  # the estimate while pending, the actual payout once released


class ImpactRecord(BaseModel):
    job_id: str
    lot_id: str
    farmer_id: str
    farmer_name: str
    village: str | None
    district: str | None
    weight_kg: int
    settled_at: datetime | None


class ImpactOut(BaseModel):
    tonnes_diverted: float
    jobs_settled: int
    records: list[ImpactRecord]
