import { homeFor, type Role } from "./auth";

/** Every event type the API can send (api/app/services/notify_catalog.py; a test keeps them equal). */
export const NOTIFICATION_TYPES = [
  "lot.created", "lot.matched", "lot.unmatched", "lot.updated", "lot.reassigned",
  "job.funded", "offer.created", "offer.expired", "offer.declined", "job.offers_exhausted",
  "job.accepted", "job.picked_up", "job.pickup_far", "job.delivered", "job.delivery_far",
  "job.confirmed", "job.rejected", "job.settled", "job.disputed", "escalation.created",
  "escalation.resolved", "ledger.unbalanced", "order.placed", "product.low_stock",
  "account.pending", "account.approved", "account.rejected", "account.suspended",
  "account.reactivated", "account.tier_changed", "account.edited",
] as const;

/** The page a notification belongs on, for the person reading it. */
export function routeFor(type: string, role: Role): string {
  if (type === "account.tier_changed" || type === "account.edited") return "/settings";
  if (type.startsWith("order.") || type.startsWith("product.")) {
    return role === "buyer" ? "/market" : homeFor(role);
  }
  return homeFor(role);
}

/** "just now", "5 min ago", "3 h ago", "2 d ago", else the date. */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
