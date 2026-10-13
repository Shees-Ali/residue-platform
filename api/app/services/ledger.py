from app.models.ledger import LedgerEntry


def escrow_balanced(entries: list[LedgerEntry]) -> bool:
    """True when escrow_in == release_farmer + release_transporter + platform_fee + refund."""
    # TODO(A3): sum by kind and compare.
    raise NotImplementedError
