// A2 tests-first: offer expiry and the transporter ladder, mirrored from
// api/tests/test_offer_expiry.py.
import { describe, expect, test } from "vitest";
import { isOfferExpired } from "../assignment";
import { nextTransporter, tickOffers } from "../dispatch";
import type { Offer, OfferStatus } from "../types";

const NOW = Date.UTC(2026, 9, 13, 12, 0, 0); // 2026-10-13 12:00 UTC
const MINUTE = 60_000;

function offer(id: string, deltaMs: number, status: OfferStatus = "pending"): Offer {
  return { id, jobId: "j1", transporterId: "t" + id, expiresAt: NOW + deltaMs, status };
}

describe("A2 offer expiry and dispatch ladder", () => {
  test("not expired before deadline", () => {
    expect(isOfferExpired(offer("1", 5 * MINUTE), NOW)).toBe(false);
  });

  test("expired at and after deadline", () => {
    expect(isOfferExpired(offer("1", 0), NOW)).toBe(true);
    expect(isOfferExpired(offer("1", -MINUTE), NOW)).toBe(true);
  });

  test("accepted offer never expires", () => {
    expect(isOfferExpired(offer("1", -60 * MINUTE, "accepted"), NOW)).toBe(false);
  });

  test("tick returns only expired pending offers", () => {
    const offers = [offer("1", -MINUTE), offer("2", MINUTE)];
    expect(tickOffers(offers, NOW)).toEqual(["1"]);
  });

  test("next transporter skips tried", () => {
    expect(nextTransporter(["a", "b", "c"], ["a", "b"])).toBe("c");
    expect(nextTransporter(["a"], ["a"])).toBeNull();
  });
});
