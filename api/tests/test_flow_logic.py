"""Pure logic shared by the dispatch, settlement and quote flows."""
import pytest

from app.models.ledger import LedgerEntry
from app.services.dispatch import TransporterCandidate, rank_transporters
from app.services.economics import Shares, get_shares, gross, payouts
from app.services.job_states import (
    TERMINAL,
    TRANSITIONS,
    InvalidTransition,
    can_transition,
    require_transition,
)
from app.services.ledger import escrow_balanced
from app.services.revenue_share import split

# --- state machine -------------------------------------------------------------------------


def test_happy_path_is_allowed_in_order():
    path = ["created", "funded", "offered", "accepted", "picked_up", "delivered", "confirmed",
            "settled"]
    for a, b in zip(path, path[1:], strict=False):
        assert can_transition(a, b), (a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [("created", "offered"), ("funded", "accepted"), ("accepted", "delivered"),
     ("delivered", "settled"), ("settled", "funded"), ("rejected", "delivered")],
)
def test_skipping_or_reversing_is_rejected(a, b):
    assert not can_transition(a, b)
    with pytest.raises(InvalidTransition):
        require_transition(a, b)


def test_side_paths_and_terminal_states():
    assert can_transition("offered", "funded")  # ladder exhausted
    assert can_transition("delivered", "rejected")
    assert can_transition("confirmed", "disputed")
    assert all(not TRANSITIONS[s] for s in TERMINAL)


def test_every_state_in_the_table_is_a_known_db_state():
    from app.db_models.base import JOB_STATES

    assert set(TRANSITIONS) == set(JOB_STATES) - {"verified"}


# --- transporter ranking ----------------------------------------------------------------------


def tc(id_, lat, lon, max_t=10, approved=True):
    return TransporterCandidate(id_, lat, lon, max_t, approved)


def test_nearest_approved_transporter_first():
    ranked = rank_transporters(
        [tc("far", 32.5, 75.0), tc("near", 31.51, 74.31), tc("mid", 31.8, 74.5)], 31.5, 74.3, 5
    )
    assert ranked == ["near", "mid", "far"]


def test_unapproved_and_too_small_transporters_are_skipped():
    ranked = rank_transporters(
        [tc("a", 31.5, 74.3, approved=False), tc("b", 31.5, 74.3, max_t=3), tc("c", 31.6, 74.4)],
        31.5, 74.3, 5,
    )
    assert ranked == ["c"]


def test_ranking_ties_are_stable_by_id():
    ranked = rank_transporters([tc("b", 31.5, 74.3), tc("a", 31.5, 74.3)], 31.5, 74.3, 1)
    assert ranked == ["a", "b"]


# --- money ------------------------------------------------------------------------------------


def test_gross_rounds_half_up_to_whole_paisa():
    assert gross(1000, 500_000) == 500_000
    assert gross(2500, 500_000) == 1_250_000
    assert gross(1, 500) == 1  # 0.5 rounds up
    assert gross(0, 500_000) == 0


@pytest.mark.parametrize("total", [0, 1, 3, 999, 1_250_001, 7_777_777])
def test_payouts_always_sum_to_the_total(total):
    parts = payouts(total, Shares(transporter_bps=2000, platform_bps=1000))
    assert sum(parts.values()) == total
    assert set(parts) == {"farmer", "transporter", "platform"}


def test_default_shares_are_70_20_10(monkeypatch):
    monkeypatch.delenv("SHARE_TRANSPORTER_BPS", raising=False)
    monkeypatch.delenv("SHARE_PLATFORM_BPS", raising=False)
    s = get_shares()
    assert (s.farmer_bps, s.transporter_bps, s.platform_bps) == (7000, 2000, 1000)


def test_shares_over_100_percent_are_refused(monkeypatch):
    monkeypatch.setenv("SHARE_TRANSPORTER_BPS", "9000")
    monkeypatch.setenv("SHARE_PLATFORM_BPS", "2000")
    with pytest.raises(ValueError):
        get_shares()


def test_split_gives_leftover_units_to_the_largest_remainders():
    # 10 split 3333/3333/3334: floors 3,3,3 leave 1 unit, which goes to the largest remainder
    assert split(10, {"a": 3333, "b": 3333, "c": 3334}) == {"a": 3, "b": 3, "c": 4}


def test_split_rejects_negative_amounts():
    with pytest.raises(ValueError):
        split(-1, {"a": 10000})


def test_a_full_settlement_balances_the_ledger():
    total = gross(2750, 640_000)
    parts = payouts(total, get_shares())
    entries = [
        LedgerEntry(job_id="j", kind="escrow_in", amount=total),
        LedgerEntry(job_id="j", kind="release_farmer", amount=parts["farmer"]),
        LedgerEntry(job_id="j", kind="release_transporter", amount=parts["transporter"]),
        LedgerEntry(job_id="j", kind="platform_fee", amount=parts["platform"]),
    ]
    assert escrow_balanced(entries)
