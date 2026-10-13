from datetime import datetime

from app.models.factory import Factory, LotRequest
from app.models.offer import Offer


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # TODO(A1)
    raise NotImplementedError


def score_factory(factory: Factory, lot: LotRequest) -> float | None:
    """Score a factory for a lot (higher is better); None if it does not accept the residue type.

    Inputs: residue type accepted, haversine distance, price.
    """
    # TODO(A1)
    raise NotImplementedError


def rank_factories(factories: list[Factory], lot: LotRequest) -> list[Factory]:
    # TODO(A1): drop ineligible, sort by score descending.
    raise NotImplementedError


def is_offer_expired(offer: Offer, now: datetime) -> bool:
    # TODO(A2): expired when now >= offer.expires_at and status is pending.
    raise NotImplementedError
