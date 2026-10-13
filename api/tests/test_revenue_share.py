import pytest

from app.services.revenue_share import BPS_TOTAL, split

pytestmark = pytest.mark.tdd  # FA3: remove when implemented

SHARES = {"farmer": 5000, "factory": 3000, "ngo": 500, "platform": 1500}


@pytest.mark.parametrize("total", [0, 1, 7, 100, 9_999, 1_000_003])
def test_parts_sum_to_total(total):
    assert sum(split(total, SHARES).values()) == total


def test_shares_in_bps_sum_to_100_percent():
    assert sum(SHARES.values()) == BPS_TOTAL


def test_exact_split():
    assert split(10_000, SHARES) == SHARES


def test_rejects_shares_not_summing_to_100_percent():
    with pytest.raises(ValueError):
        split(100, {"farmer": 5000, "platform": 4000})
