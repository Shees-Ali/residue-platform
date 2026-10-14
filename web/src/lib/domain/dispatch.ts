// A2: offer expiry sweep and the transporter ladder
// (mirrors api/app/services/dispatch.py). Pure — callers pass `nowMs` so the
// demo can fast-forward time without sleeping.
import { haversineKm, isOfferExpired } from "./assignment";
import type { Offer, Transporter } from "./types";

/**
 * Ids of offers that have lapsed: pending and past their deadline. Accepted
 * offers are never swept (isOfferExpired guards on status), so a taken job is
 * not re-dispatched out from under the transporter who accepted it.
 */
export function tickOffers(offers: Offer[], nowMs: number): string[] {
  return offers.filter((o) => isOfferExpired(o, nowMs)).map((o) => o.id);
}

/**
 * The next transporter to try, walking the ranked ladder while skipping those
 * already offered. Returns null when the ladder is exhausted — the caller then
 * leaves the job offered-but-unclaimed for admin attention (A2 side path).
 */
export function nextTransporter(
  rankedIds: string[],
  alreadyOfferedIds: string[],
): string | null {
  const tried = new Set(alreadyOfferedIds);
  for (const id of rankedIds) {
    if (!tried.has(id)) return id;
  }
  return null;
}

/**
 * Rank approved transporters by proximity to the pickup point. Unapproved
 * transporters are dropped — approval (A2) gates who receives work. Ties break
 * by id so the ladder is deterministic for the same inputs.
 */
export function rankTransporters(
  transporters: Transporter[],
  lat: number,
  lon: number,
): string[] {
  return transporters
    .filter((t) => t.approved)
    .map((t) => ({ id: t.id, km: haversineKm(lat, lon, t.lat, t.lon) }))
    .sort((a, b) => a.km - b.km || a.id.localeCompare(b.id))
    .map((t) => t.id);
}
