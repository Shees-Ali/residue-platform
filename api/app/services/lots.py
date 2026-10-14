"""Pure lot logic for F1: no database, no HTTP. Tests in tests/test_lots_service.py."""
import difflib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from app.services.places import DISTRICTS

# Pakistan has used a fixed UTC+5 since 2009 (no DST), so no tz database is needed.
PKT = timezone(timedelta(hours=5), "PKT")

PICKUP_PARTS: dict[str, tuple[time, time]] = {
    "morning": (time(6), time(12)),
    "afternoon": (time(12), time(17)),
    "evening": (time(17), time(20)),
}
MAX_QUANTITY_TONNES = 100
MAX_DAYS_AHEAD = 60
FUZZY_CUTOFF = 0.8


class LotError(Exception):
    """A request the farmer can fix. Returned to the agent as 422 {error, message, valid}."""

    def __init__(self, code: str, message: str, valid: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.valid = valid or []


@dataclass(frozen=True)
class VillageRow:
    id: object
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class PlaceMatch:
    village_id: object | None
    village: str
    district: str
    lat: float
    lon: float
    match: str  # exact | fuzzy | district


def validate_quantity(value: float) -> Decimal:
    if not isinstance(value, int | float) or not 0 < value <= MAX_QUANTITY_TONNES:
        raise LotError(
            "invalid_quantity",
            f"quantity_tonnes must be more than 0 and at most {MAX_QUANTITY_TONNES}",
        )
    return Decimal(str(value)).quantize(Decimal("0.01"))


def validate_residue(code: str, valid: dict[str, str]) -> str:
    """`valid` maps residue code -> label. Accepts the code in any case."""
    key = (code or "").strip().lower().replace(" ", "_")
    if key not in valid:
        raise LotError("unknown_residue_type", f"Unknown residue type '{code}'", sorted(valid))
    return key


def pickup_window(
    pickup_date: str, part: str, today: date | None = None
) -> tuple[datetime, datetime]:
    """(from, to) in UTC for a date and part of day, interpreted in Pakistan time."""
    today = today or datetime.now(PKT).date()
    part_key = (part or "").strip().lower()
    if part_key not in PICKUP_PARTS:
        raise LotError("invalid_pickup_part", f"Unknown pickup part '{part}'", list(PICKUP_PARTS))
    try:
        day = date.fromisoformat((pickup_date or "").strip())
    except ValueError:
        raise LotError(
            "invalid_pickup_date", "pickup_date must be an ISO date, YYYY-MM-DD"
        ) from None
    if day < today:
        raise LotError("pickup_date_in_past", f"pickup_date {day} is in the past")
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise LotError("pickup_date_too_far", f"pickup_date must be within {MAX_DAYS_AHEAD} days")
    start, end = PICKUP_PARTS[part_key]
    return (
        datetime.combine(day, start, tzinfo=PKT).astimezone(UTC),
        datetime.combine(day, end, tzinfo=PKT).astimezone(UTC),
    )


def pickup_text(start: datetime, end: datetime) -> str:
    s, e = start.astimezone(PKT), end.astimezone(PKT)
    return f"{s:%d %b %Y}, {s:%H:%M} to {e:%H:%M}"


def canonical_district(name: str) -> str:
    key = (name or "").strip().lower()
    by_lower = {d.lower(): d for d in DISTRICTS}
    if key in by_lower:
        return by_lower[key]
    close = difflib.get_close_matches(key, list(by_lower), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return by_lower[close[0]]
    raise LotError("unknown_district", f"Unknown district '{name}'", sorted(DISTRICTS))


def match_place(village: str, district: str, villages: list[VillageRow]) -> PlaceMatch:
    """Exact (case-insensitive) match in the district, then fuzzy, else the district centroid."""
    canon = canonical_district(district)
    wanted = (village or "").strip().lower()
    by_lower = {v.name.lower(): v for v in villages}
    if wanted in by_lower:
        v = by_lower[wanted]
        return PlaceMatch(v.id, v.name, canon, v.lat, v.lon, "exact")
    close = difflib.get_close_matches(wanted, list(by_lower), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        v = by_lower[close[0]]
        return PlaceMatch(v.id, v.name, canon, v.lat, v.lon, "fuzzy")
    lat, lon = DISTRICTS[canon]
    return PlaceMatch(None, (village or "").strip(), canon, lat, lon, "district")
