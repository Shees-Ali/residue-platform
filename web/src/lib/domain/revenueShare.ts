// FA3: the four-way revenue split (mirrors api/app/services/revenue_share.py).
// Uses the largest-remainder method so the parts always sum to the total exactly
// — no paisa is created or destroyed by rounding. Shares are basis points that
// must total BPS_TOTAL (10000 = 100%).
export const BPS_TOTAL = 10000;

export interface Shares {
  farmer: number;
  factory: number;
  ngo: number;
  platform: number;
}

/** Default split: farmer 50%, factory 30%, ngo 5%, platform 15%. */
export const DEFAULT_SHARES: Shares = {
  farmer: 5000,
  factory: 3000,
  ngo: 500,
  platform: 1500,
};

/**
 * Split `totalCents` (paisa) across the shares. Each party first gets its
 * floor(total * bps / BPS_TOTAL); the leftover paisa go one at a time to the
 * parties with the largest fractional remainders, largest first, ties broken
 * by a stable key order. Guarantees sum(parts) === totalCents.
 *
 * Throws if the shares do not total exactly BPS_TOTAL — a misconfigured split
 * must fail loudly rather than silently shortchange someone.
 */
export function split(totalCents: number, shares: Shares): Record<string, number> {
  assertSharesValid(shares);

  const keys = Object.keys(shares) as (keyof Shares)[];
  const parts: Record<string, number> = {};
  const remainders: { key: string; remainder: number }[] = [];

  let allocated = 0;
  for (const key of keys) {
    const exact = (totalCents * shares[key]) / BPS_TOTAL;
    const floor = Math.floor(exact);
    parts[key] = floor;
    allocated += floor;
    remainders.push({ key, remainder: exact - floor });
  }

  let leftover = totalCents - allocated;
  // Largest fractional remainder first; stable order for exact ties.
  remainders.sort((a, b) => b.remainder - a.remainder);
  for (const { key } of remainders) {
    if (leftover <= 0) break;
    parts[key] += 1;
    leftover -= 1;
  }

  return parts;
}

function assertSharesValid(shares: Shares): void {
  const total = Object.values(shares).reduce((a, b) => a + b, 0);
  if (total !== BPS_TOTAL) {
    throw new Error(
      `revenue shares must sum to ${BPS_TOTAL} bps, got ${total}`,
    );
  }
}
