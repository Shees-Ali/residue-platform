import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import { unwrap } from "./query";
import { DISTRICTS, RESIDUES } from "@/lib/places";

export const LOTS_KEY = ["lots"] as const;
export const JOBS_KEY = ["jobs"] as const;
export const OFFERS_KEY = ["offers"] as const;
export const PAYOUTS_KEY = ["payouts"] as const;
export const STATS_KEY = ["stats"] as const;
export const TRANSPORTERS_KEY = ["transporters"] as const;
export const TRACK_KEY = ["track"] as const;
export const ACTIVE_TRACKS_KEY = ["tracking-active"] as const;
export const LEDGER_KEY = ["ledger"] as const;
export const IMPACT_KEY = ["impact"] as const;
export const PRODUCTS_KEY = ["products"] as const;
export const ORDERS_KEY = ["orders"] as const;
export const ESCALATIONS_KEY = ["escalations"] as const;

const POLL = 8_000; // events are a no-op locally, so live screens poll

/** The signed-in person's lots: a farmer sees their own, an admin sees all. Refreshes itself. */
export function useLots() {
  return useQuery({
    queryKey: LOTS_KEY,
    queryFn: () => unwrap(api.GET("/api/lots")),
    refetchInterval: 10_000,
  });
}

/** Jobs the caller may see (factory: its own, transporter: assigned ones, farmer: own lots,
 * admin: all), optionally in one state. */
export function useJobs(state?: string) {
  return useQuery({
    queryKey: [...JOBS_KEY, state ?? "all"],
    queryFn: () => unwrap(api.GET("/api/jobs", { params: { query: { state, limit: 200 } } })),
    refetchInterval: POLL,
  });
}

/** The transporter's offers. Polled quickly because each one has a short clock. */
export function useOffers() {
  return useQuery({
    queryKey: OFFERS_KEY,
    queryFn: () => unwrap(api.GET("/api/offers")),
    refetchInterval: 4_000,
  });
}

/** Payouts for the signed-in transporter or farmer: pending until released. */
export function useMyPayouts() {
  return useQuery({
    queryKey: PAYOUTS_KEY,
    queryFn: () => unwrap(api.GET("/api/ledger/mine")),
    refetchInterval: POLL,
  });
}

export function useStats() {
  return useQuery({
    queryKey: STATS_KEY,
    queryFn: () => unwrap(api.GET("/api/stats")),
    refetchInterval: POLL,
  });
}

/** Moving loads with their last position (admin: all, factory: its own). */
export function useActiveTracks() {
  return useQuery({
    queryKey: ACTIVE_TRACKS_KEY,
    queryFn: () => unwrap(api.GET("/api/tracking/active")),
    refetchInterval: 10_000,
  });
}

/** The map data for one job: farm, factory, the path so far and a rough arrival time. */
export function useTrack(jobId: string | undefined) {
  return useQuery({
    queryKey: [...TRACK_KEY, jobId],
    queryFn: () => unwrap(api.GET("/api/jobs/{job_id}/track", { params: { path: { job_id: jobId! } } })),
    enabled: Boolean(jobId),
    refetchInterval: 10_000,
  });
}

/** The whole ledger, newest first, `limit` entries from `offset` (admin). */
export function useLedger(offset: number, limit = 15) {
  return useQuery({
    queryKey: [...LEDGER_KEY, offset, limit],
    queryFn: () => unwrap(api.GET("/api/ledger", { params: { query: { offset, limit } } })),
    refetchInterval: POLL,
    placeholderData: (previous) => previous,
  });
}

/** Does escrow in equal everything paid out, kept and refunded? (admin) */
export function useLedgerCheck() {
  return useQuery({
    queryKey: [...LEDGER_KEY, "check"],
    queryFn: () => unwrap(api.GET("/api/ledger/check")),
    refetchInterval: POLL,
  });
}

export function useImpact() {
  return useQuery({
    queryKey: IMPACT_KEY,
    queryFn: () => unwrap(api.GET("/api/impact", { params: { query: { limit: 10 } } })),
    refetchInterval: 15_000,
  });
}

export function useEscalations() {
  return useQuery({
    queryKey: ESCALATIONS_KEY,
    queryFn: () => unwrap(api.GET("/api/escalations")),
    refetchInterval: POLL,
  });
}

export function useJobLedger(jobId: string | undefined) {
  return useQuery({
    queryKey: [...LEDGER_KEY, "job", jobId],
    queryFn: () => unwrap(api.GET("/api/jobs/{job_id}/ledger", { params: { path: { job_id: jobId! } } })),
    enabled: Boolean(jobId),
  });
}

/** Products: a buyer or admin sees what is for sale; a factory sees all of its own. */
export function useProducts() {
  return useQuery({
    queryKey: PRODUCTS_KEY,
    queryFn: () => unwrap(api.GET("/api/products")),
    refetchInterval: 15_000,
  });
}

/** Orders: a buyer's own, a factory's for its products, or all (admin). */
export function useOrders() {
  return useQuery({
    queryKey: ORDERS_KEY,
    queryFn: () => unwrap(api.GET("/api/orders")),
    refetchInterval: POLL,
  });
}

export function useTransporters() {
  return useQuery({
    queryKey: TRANSPORTERS_KEY,
    queryFn: () => unwrap(api.GET("/api/transporters")),
    refetchInterval: POLL,
  });
}

// Reference lists: the API is the source; the built-in lists cover the moment before it answers.
export function useResidueTypes() {
  const q = useQuery({
    queryKey: ["residue-types"],
    queryFn: () => unwrap(api.GET("/api/residue-types")),
    staleTime: 10 * 60_000,
  });
  return q.data?.length ? q.data : RESIDUES;
}

export function useDistricts(): readonly string[] {
  const q = useQuery({
    queryKey: ["districts"],
    queryFn: () => unwrap(api.GET("/api/districts")),
    staleTime: 10 * 60_000,
  });
  return q.data?.length ? q.data : DISTRICTS;
}

/** Known village names in a district, for suggestions. Any other name is still accepted. */
export function useVillages(district: string) {
  const q = useQuery({
    queryKey: ["villages", district],
    queryFn: () => unwrap(api.GET("/api/villages", { params: { query: { district } } })),
    enabled: Boolean(district),
    staleTime: 10 * 60_000,
    meta: { silent: true }, // suggestions are optional, so a failure is not worth a toast
  });
  return q.data?.map((v) => v.name) ?? [];
}
