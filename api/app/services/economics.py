"""Money math shared by quotes, funding and settlement, so they cannot disagree. Pure.

Everything is integer minor units (paisa) and basis points. See memory/backend-flows.md.
"""
import os
from dataclasses import dataclass

from app.services.revenue_share import BPS_TOTAL, split


@dataclass(frozen=True)
class Shares:
    transporter_bps: int
    platform_bps: int

    @property
    def farmer_bps(self) -> int:
        return BPS_TOTAL - self.transporter_bps - self.platform_bps

    def as_dict(self) -> dict[str, int]:
        return {
            "farmer": self.farmer_bps,
            "transporter": self.transporter_bps,
            "platform": self.platform_bps,
        }


def get_shares() -> Shares:
    """Read at call time so tests and deploys can override with SHARE_*_BPS."""
    transporter = int(os.getenv("SHARE_TRANSPORTER_BPS", "2000"))
    platform = int(os.getenv("SHARE_PLATFORM_BPS", "1000"))
    shares = Shares(transporter, platform)
    if min(shares.farmer_bps, transporter, platform) < 0:
        raise ValueError("SHARE_* values must be non-negative and sum to at most 10000")
    return shares


def job_shares(farmer_share_bps: int) -> Shares:
    """Shares for one job: the farmer's cut is fixed when the job is created (it is what the farmer
    was quoted), the transporter's comes from config, and the platform keeps the remainder."""
    transporter = get_shares().transporter_bps
    platform = BPS_TOTAL - farmer_share_bps - transporter
    if platform < 0:
        raise ValueError("job farmer share plus transporter share exceeds 100%")
    return Shares(transporter, platform)


def offer_ttl_seconds() -> int:
    return int(os.getenv("OFFER_TTL_SECONDS", "120"))


def gross(weight_kg: int, price_per_tonne: int) -> int:
    """Value of `weight_kg` at a per-tonne price, rounded half up to a whole paisa."""
    return (weight_kg * price_per_tonne + 500) // 1000


def payouts(total: int, shares: Shares) -> dict[str, int]:
    """{farmer, transporter, platform} amounts that sum to exactly `total`."""
    return split(total, shares.as_dict())


def sale_shares() -> dict[str, int]:
    """Four-way split of a product sale (FA3). Assumed defaults; override with SALE_SHARE_*_BPS."""
    shares = {
        "farmer": int(os.getenv("SALE_SHARE_FARMER_BPS", "5000")),
        "factory": int(os.getenv("SALE_SHARE_FACTORY_BPS", "3000")),
        "ngo": int(os.getenv("SALE_SHARE_NGO_BPS", "500")),
        "platform": int(os.getenv("SALE_SHARE_PLATFORM_BPS", "1500")),
    }
    if sum(shares.values()) != BPS_TOTAL:
        raise ValueError(f"SALE_SHARE_* values must sum to {BPS_TOTAL}")
    return shares
