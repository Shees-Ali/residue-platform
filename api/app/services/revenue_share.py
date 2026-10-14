BPS_TOTAL = 10_000


def split(total_cents: int, shares_bps: dict[str, int]) -> dict[str, int]:
    """Split `total_cents` by basis-point shares; parts sum to exactly `total_cents`.

    shares_bps must sum to BPS_TOTAL (e.g. farmer, factory, ngo, platform). Largest-remainder
    rounding: each party gets the floor of its share, then the leftover units go one each to the
    parties with the biggest fractional remainders (ties go to the earlier key).
    """
    if total_cents < 0:
        raise ValueError("total must not be negative")
    if any(bps < 0 for bps in shares_bps.values()):
        raise ValueError("shares must not be negative")
    if sum(shares_bps.values()) != BPS_TOTAL:
        raise ValueError(f"shares must sum to {BPS_TOTAL} bps")
    parts = {k: total_cents * bps // BPS_TOTAL for k, bps in shares_bps.items()}
    leftover = total_cents - sum(parts.values())
    by_remainder = sorted(
        enumerate(shares_bps.items()),
        key=lambda item: (-(total_cents * item[1][1] % BPS_TOTAL), item[0]),
    )
    for _, (key, _bps) in by_remainder[:leftover]:
        parts[key] += 1
    return parts
