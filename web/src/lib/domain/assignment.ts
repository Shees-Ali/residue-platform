// A1: factory scoring and ranking (mirrors api/app/services/assignment.py).
// Pure functions, no I/O. Scoring weights distance against price so the demo
// engine and the future API produce identical rankings for the same inputs.
import type { Factory, LotRequest, Offer, RankedFactory } from "./types";

const EARTH_RADIUS_KM = 6371;

/** Great-circle distance between two lat/lon points, in kilometres. */
export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
}

export function factoryDistanceKm(factory: Factory, lot: LotRequest): number {
  return haversineKm(lot.lat, lot.lon, factory.lat, factory.lon);
}

// Higher is better. Ineligible factories return null (filtered out of ranks).
// Score = value term + proximity term. The value term is the lot's gross worth
// to the factory (price per tonne x tonnes, in paisa, scaled down) so bigger,
// richer lots pull harder; the proximity term rewards closeness. Both terms are
// unit-consistent and demo-tuned, not learned.
const DISTANCE_WEIGHT = 10; // km scale for the proximity falloff
const VALUE_SCALE = 100_000; // paisa -> comparable magnitude to proximity [0,1]

export function scoreFactory(factory: Factory, lot: LotRequest): number | null {
  if (!factory.acceptedResidues.includes(lot.residueType)) return null;
  const distanceKm = factoryDistanceKm(factory, lot);
  // Proximity term in [0, 1]: 1 at zero distance, decaying toward 0 as the
  // factory gets farther, so closer always scores higher at equal price.
  const proximity = DISTANCE_WEIGHT / (distanceKm + DISTANCE_WEIGHT);
  const lotValuePaisa =
    factory.pricePerTonneCents * (lot.quantityTonnes || 1);
  const valueTerm = lotValuePaisa / VALUE_SCALE;
  return valueTerm + proximity;
}

/** Eligible factories, best first. Ineligible ones are dropped. */
export function rankFactories(
  factories: Factory[],
  lot: LotRequest,
): RankedFactory[] {
  const ranked: RankedFactory[] = [];
  for (const factory of factories) {
    const score = scoreFactory(factory, lot);
    if (score === null) continue;
    ranked.push({
      factory,
      score,
      distanceKm: factoryDistanceKm(factory, lot),
    });
  }
  return ranked.sort((a, b) => b.score - a.score);
}

/**
 * A2: an offer expires once its deadline passes. Boundary is inclusive
 * (now >= expiresAt), and only pending offers ever expire — an accepted
 * offer is locked in regardless of how much time has elapsed.
 */
export function isOfferExpired(offer: Offer, nowMs: number): boolean {
  if (offer.status !== "pending") return false;
  return nowMs >= offer.expiresAt;
}
