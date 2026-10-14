"""A2 offer ladder, pure. The caller loads rows, calls these, then persists the result."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models.offer import Offer
from app.services.assignment import haversine_km, is_offer_expired

# The approval tier sets the largest lot a transporter is offered (tonnes).
TIER_MAX_TONNES = {1: 3, 2: 7, 3: 15}


@dataclass(frozen=True)
class TransporterCandidate:
    id: str
    lat: float
    lon: float
    max_tonnes: Decimal | float
    approved: bool


def next_transporter(ranked_ids: list[str], tried_ids: list[str]) -> str | None:
    """First ranked transporter that has not been offered this job yet."""
    tried = set(tried_ids)
    return next((t for t in ranked_ids if t not in tried), None)


def tick(offers: list[Offer], now: datetime) -> list[str]:
    """Return ids of pending offers to expire at `now` (caller persists and re-offers)."""
    return [o.id for o in offers if is_offer_expired(o, now)]


def rank_transporters(
    candidates: list[TransporterCandidate], lat: float, lon: float, tonnes: float
) -> list[str]:
    """Approved transporters whose tier can carry `tonnes`, nearest to the pickup first."""
    eligible = [c for c in candidates if c.approved and float(c.max_tonnes) >= tonnes]
    eligible.sort(key=lambda c: (haversine_km(lat, lon, c.lat, c.lon), c.id))
    return [c.id for c in eligible]
