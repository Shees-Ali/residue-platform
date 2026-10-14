"""A1 factory scoring and A2 offer expiry. Pure: no database, no clock (callers pass `now`)."""
import math
from datetime import datetime

from app.models.factory import Factory, LotRequest
from app.models.offer import Offer

EARTH_RADIUS_KM = 6371.0

# Hauling cost used to compare factories: paisa per tonne per km (assumed; backend-flows.md).
TRANSPORT_COST_PER_TONNE_KM = 2_500


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def score_factory(factory: Factory, lot: LotRequest) -> float | None:
    """Score a factory for a lot (higher is better); None if it does not accept the residue type.

    Net delivered price per tonne: what the factory pays minus the cost of hauling one tonne there.
    So a nearer factory wins at equal price and a better price wins at equal distance.
    """
    if lot.residue_type not in factory.accepted_residues:
        return None
    distance = haversine_km(lot.lat, lot.lon, factory.lat, factory.lon)
    return factory.price_per_tonne_cents - distance * TRANSPORT_COST_PER_TONNE_KM


def rank_factories(factories: list[Factory], lot: LotRequest) -> list[Factory]:
    """Drop ineligible factories, best first. Ties break on id so the order is stable."""
    scored = [(score_factory(f, lot), f) for f in factories]
    eligible = [(s, f) for s, f in scored if s is not None]
    eligible.sort(key=lambda sf: (-sf[0], sf[1].id))
    return [f for _, f in eligible]


def is_offer_expired(offer: Offer, now: datetime) -> bool:
    """Expired when the offer is still pending and its deadline has been reached."""
    return offer.status == "pending" and now >= offer.expires_at
