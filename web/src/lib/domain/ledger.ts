// A3: the escrow invariant (mirrors api/app/services/ledger.py).
// Money in must equal money out: every rupee that entered escrow is either
// released to a party or refunded. This is the check the admin screen shows,
// and it must never pass by luck — a real shortfall (weight disputed, fee not
// yet released) legitimately fails it, which is the point.
import type { LedgerEntry } from "./types";

// The only kind that puts money IN. Everything else takes money out.
const INFLOW_KINDS = new Set(["escrow_in"]);

export function totalIn(entries: LedgerEntry[]): number {
  return sum(entries.filter((e) => INFLOW_KINDS.has(e.kind)));
}

export function totalOut(entries: LedgerEntry[]): number {
  return sum(entries.filter((e) => !INFLOW_KINDS.has(e.kind)));
}

/**
 * True when escrow in equals everything released plus fees plus refunds.
 * An empty ledger is trivially balanced (nothing in, nothing out) — the demo
 * starts with one settled job so this is visible as true on first load.
 */
export function escrowBalanced(entries: LedgerEntry[]): boolean {
  return totalIn(entries) === totalOut(entries);
}

function sum(entries: LedgerEntry[]): number {
  let total = 0;
  for (const e of entries) total += e.amountCents;
  return total;
}
