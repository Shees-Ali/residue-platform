// FA3 tests-first: the four-way revenue split, mirrored from
// api/tests/test_revenue_share.py. Parts must sum to the total exactly
// (largest-remainder rounding); shares are basis points summing to 10000.
import { describe, expect, test } from "vitest";
import { BPS_TOTAL, split, type Shares } from "../revenueShare";

const SHARES = { farmer: 5000, factory: 3000, ngo: 500, platform: 1500 };

describe("FA3 revenue split", () => {
  test.each([0, 1, 7, 100, 9999, 1000003])("parts sum to total %i", (total) => {
    const parts = split(total, SHARES);
    expect(Object.values(parts).reduce((a, b) => a + b, 0)).toBe(total);
  });

  test("shares in bps sum to 100 percent", () => {
    expect(Object.values(SHARES).reduce((a, b) => a + b, 0)).toBe(BPS_TOTAL);
  });

  test("exact split", () => {
    expect(split(10_000, SHARES)).toEqual(SHARES);
  });

  test("rejects shares not summing to 100 percent", () => {
    // Deliberately malformed (partial, sums to 9000): a cast marks it as an
    // intentionally invalid input, which is exactly what must throw.
    const bad = { farmer: 5000, platform: 4000 } as unknown as Shares;
    expect(() => split(100, bad)).toThrow();
  });
});
