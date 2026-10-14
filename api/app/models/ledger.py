from typing import Literal

from pydantic import BaseModel

LedgerKind = Literal[
    "escrow_in", "release_farmer", "release_transporter", "platform_fee", "refund",
    "release_factory", "release_ngo",
]


class LedgerEntry(BaseModel):
    job_id: str
    kind: LedgerKind
    amount: int  # integer minor units, always >= 0
