/** What a quiet platform answers. Lists default to empty; these endpoints return one object. */
export const OBJECT_DEFAULTS: Record<string, unknown> = {
  "/api/stats": {
    farmers: 0, factories: 0, transporters: 0, transporters_waiting_approval: 0, live_jobs: 0,
    jobs_settled: 0, orders: 0, tonnes_diverted: 0, escrow_held: 0, open_escalations: 0,
  },
  "/api/ledger/check": {
    balanced: true, jobs_checked: 0, orders_checked: 0, unbalanced_jobs: [], unbalanced_orders: [],
    held_in_escrow: 0, totals: {},
  },
  "/api/impact": { tonnes_diverted: 0, jobs_settled: 0, records: [] },
};

export const quiet = (path: string): unknown => OBJECT_DEFAULTS[path] ?? [];
