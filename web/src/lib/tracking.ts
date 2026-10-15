import type { components } from "@/api/schema";

export type Track = components["schemas"]["TrackOut"];
export type ActiveTrack = components["schemas"]["ActiveTrack"];

/** "12 s ago", "3 min ago": how fresh the last position is. */
export function ago(iso: string, now: number = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

/** A sentence about where the load is going and when it should get there (a rough estimate). */
export function arrivalText(t: {
  heading_to?: string | null;
  distance_to_target_km?: number | null;
  eta_minutes?: number | null;
  last?: { at: string } | null;
}): string {
  if (!t.last) return "No position shared yet";
  if (!t.heading_to || t.distance_to_target_km == null || t.eta_minutes == null) {
    return `Last seen ${ago(t.last.at)}`;
  }
  const where = t.heading_to === "pickup" ? "the farm" : "the factory";
  return `About ${t.eta_minutes} min and ${t.distance_to_target_km} km to ${where} (straight line). Last seen ${ago(t.last.at)}.`;
}

/** Badges for a reading that was recorded far from where it should have been. */
export function offSiteNotes(t: { pickup_off_site_m?: number | null; delivery_off_site_m?: number | null }): string[] {
  const notes: string[] = [];
  const far = (m: number | null | undefined) => m != null && m > 25_000;
  if (far(t.pickup_off_site_m)) notes.push(`Pickup recorded ${Math.round(t.pickup_off_site_m! / 1000)} km from the farm`);
  if (far(t.delivery_off_site_m)) {
    notes.push(`Delivery recorded ${Math.round(t.delivery_off_site_m! / 1000)} km from the factory`);
  }
  return notes;
}
