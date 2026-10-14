// A3 tests-first: the escrow invariant, mirrored from api/tests/test_ledger.py.
import { describe, expect, test } from "vitest";
import { escrowBalanced } from "../ledger";
import type { LedgerEntry, LedgerKind } from "../types";

function e(kind: LedgerKind, amountCents: number): LedgerEntry {
  return { id: kind + amountCents, jobId: "j1", kind, amountCents };
}

describe("A3 ledger invariant", () => {
  test("balanced when escrow equals releases, fees and refunds", () => {
    const entries = [
      e("escrow_in", 1000),
      e("release_farmer", 600),
      e("release_transporter", 250),
      e("platform_fee", 100),
      e("refund", 50),
    ];
    expect(escrowBalanced(entries)).toBe(true);
  });

  test("unbalanced when money missing", () => {
    expect(escrowBalanced([e("escrow_in", 1000), e("release_farmer", 600)])).toBe(false);
  });

  test("unbalanced when over released", () => {
    expect(escrowBalanced([e("escrow_in", 100), e("release_farmer", 200)])).toBe(false);
  });

  test("empty ledger is balanced", () => {
    expect(escrowBalanced([])).toBe(true);
  });
});
