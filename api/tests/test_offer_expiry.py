from datetime import UTC, datetime, timedelta

from app.models.offer import Offer
from app.services.assignment import is_offer_expired
from app.services.dispatch import next_transporter, tick

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def offer(id_, delta, status="pending"):
    return Offer(
        id=id_, job_id="j1", transporter_id="t" + id_, expires_at=NOW + delta, status=status
    )


def test_not_expired_before_deadline():
    assert is_offer_expired(offer("1", timedelta(minutes=5)), NOW) is False


def test_expired_at_and_after_deadline():
    assert is_offer_expired(offer("1", timedelta(0)), NOW) is True
    assert is_offer_expired(offer("1", -timedelta(minutes=1)), NOW) is True


def test_accepted_offer_never_expires():
    assert is_offer_expired(offer("1", -timedelta(hours=1), "accepted"), NOW) is False


def test_tick_returns_only_expired_pending_offers():
    offers = [offer("1", -timedelta(minutes=1)), offer("2", timedelta(minutes=1))]
    assert tick(offers, NOW) == ["1"]


def test_next_transporter_skips_tried():
    assert next_transporter(["a", "b", "c"], ["a", "b"]) == "c"
    assert next_transporter(["a"], ["a"]) is None
