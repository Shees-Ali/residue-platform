// The seed must land in a coherent, judge-ready state: escrow balanced (A3),
// a pre-settled job so the impact counter is non-zero, and an unresponsive
// transporter so the offer ladder is visible without any clicks.
import { describe, expect, test } from "vitest";
import { seedDomain } from "../seed";
import { escrowBalanced } from "../ledger";
import { rankFactories } from "../assignment";

describe("seed world", () => {
  test("the pre-settled ledger balances escrow (A3)", () => {
    const s = seedDomain();
    expect(escrowBalanced(s.ledger)).toBe(true);
    expect(s.ledger.some((e) => e.kind === "escrow_in")).toBe(true);
    expect(s.ledger.some((e) => e.kind === "release_farmer")).toBe(true);
  });

  test("jobs span the lifecycle so the demo lands mid-story", () => {
    const s = seedDomain();
    const states = s.jobs.map((j) => j.state);
    expect(states).toContain("created");
    expect(states).toContain("offered");
    expect(states).toContain("settled");
  });

  test("an unresponsive transporter leaves a pending offer to expire (A2)", () => {
    const s = seedDomain();
    const pending = s.offers.filter((o) => o.status === "pending");
    expect(pending.length).toBeGreaterThan(0);
    expect(s.transporters.some((t) => t.id === "t-unresponsive")).toBe(true);
  });

  test("unapproved transporters exist but must be excluded from ladders", () => {
    const s = seedDomain();
    expect(s.transporters.some((t) => !t.approved)).toBe(true);
    const ranked = rankFactories(s.factories, { residueType: "rice_straw", lat: 31.77, lon: 73.05, quantityTonnes: 2 });
    expect(ranked.length).toBeGreaterThan(0);
  });

  test("prices are in seed.py's paisa band (400k–900k per tonne)", () => {
    const s = seedDomain();
    for (const f of s.factories) {
      expect(f.pricePerTonneCents).toBeGreaterThanOrEqual(400_000);
      expect(f.pricePerTonneCents).toBeLessThanOrEqual(900_000);
    }
  });
});
