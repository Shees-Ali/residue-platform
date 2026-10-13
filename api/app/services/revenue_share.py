BPS_TOTAL = 10_000


def split(total_cents: int, shares_bps: dict[str, int]) -> dict[str, int]:
    """Split `total_cents` by basis-point shares; parts must sum to exactly `total_cents`.

    shares_bps must sum to BPS_TOTAL (e.g. farmer, factory, ngo, platform).
    """
    # TODO(FA3): implement with largest-remainder rounding.
    raise NotImplementedError
