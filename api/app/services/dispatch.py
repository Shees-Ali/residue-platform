from datetime import datetime

from app.models.offer import Offer


def next_transporter(ranked_ids: list[str], tried_ids: list[str]) -> str | None:
    # TODO(A2): first ranked transporter not yet tried.
    raise NotImplementedError


def tick(offers: list[Offer], now: datetime) -> list[str]:
    """Return ids of pending offers to expire at `now` (caller persists and re-offers)."""
    # TODO(A2)
    raise NotImplementedError
