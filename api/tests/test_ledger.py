import pytest

from app.models.ledger import LedgerEntry
from app.services.ledger import escrow_balanced

pytestmark = pytest.mark.tdd  # A3: remove when implemented


def e(kind, amt):
    return LedgerEntry(job_id="j1", kind=kind, amount_cents=amt)


def test_balanced_when_escrow_equals_releases_fees_refunds():
    entries = [
        e("escrow_in", 1000),
        e("release_farmer", 600),
        e("release_transporter", 250),
        e("platform_fee", 100),
        e("refund", 50),
    ]
    assert escrow_balanced(entries) is True


def test_unbalanced_when_money_missing():
    assert escrow_balanced([e("escrow_in", 1000), e("release_farmer", 600)]) is False


def test_unbalanced_when_over_released():
    assert escrow_balanced([e("escrow_in", 100), e("release_farmer", 200)]) is False


def test_empty_ledger_is_balanced():
    assert escrow_balanced([]) is True
