from collections import defaultdict

from app.models.ledger import LedgerEntry

OUT_KINDS = (
    "release_farmer", "release_transporter", "platform_fee", "refund",
    "release_factory", "release_ngo",
)


def escrow_balanced(entries: list[LedgerEntry]) -> bool:
    """True when escrow_in equals every release, fee and refund."""
    totals: dict[str, int] = defaultdict(int)
    for e in entries:
        totals[e.kind] += e.amount
    return totals["escrow_in"] == sum(totals[k] for k in OUT_KINDS)
