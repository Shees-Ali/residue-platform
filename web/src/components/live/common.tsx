import { useEffect, useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Check, Circle } from "lucide-react";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/spinner";

export type Job = components["schemas"]["JobOut"];

/** The states a job passes through, in order. The API has no separate "verified" step. */
export const STAGES: { state: string; label: string }[] = [
  { state: "created", label: "Matched" },
  { state: "funded", label: "Funded" },
  { state: "offered", label: "Offered" },
  { state: "accepted", label: "Accepted" },
  { state: "picked_up", label: "Picked up" },
  { state: "delivered", label: "Delivered" },
  { state: "confirmed", label: "Weighed" },
  { state: "settled", label: "Settled" },
];

export const STATE_LABEL: Record<string, string> = {
  ...Object.fromEntries(STAGES.map((s) => [s.state, s.label])),
  confirmed: "Weight confirmed",
  rejected: "Rejected at weigh-in",
  disputed: "Disputed, payout frozen",
};

/** Lifecycle tracker. A rejected or disputed job shows a banner, not a moving step. */
export function JobStages({ state }: { state: string }) {
  if (state === "rejected" || state === "disputed") {
    return (
      <div className="tracker" role="status">
        <div className="invariant invariant-hold">
          <span>{STATE_LABEL[state]}</span>
        </div>
      </div>
    );
  }
  const at = STAGES.findIndex((s) => s.state === state);
  return (
    <div className="tracker">
      {STAGES.map((s, i) => (
        <div className={`tracker-step ${i <= at ? "done" : ""}`} key={s.state}>
          <span>{i <= at ? <Check size={13} /> : <Circle size={11} />}</span>
          <small>{s.label}</small>
        </div>
      ))}
    </div>
  );
}

/** The current time, re-read every `ms`, for countdowns. */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

export const secondsLeft = (iso: string, now: number) =>
  Math.max(0, Math.floor((new Date(iso).getTime() - now) / 1000));

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export const when = (iso?: string | null) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "";

/** Shows the loading skeleton, a retry on failure, or the data. One shape for every live list. */
export function QueryBoundary<T>({
  q,
  children,
  what = "this list",
}: {
  q: UseQueryResult<T>;
  children: (data: T) => ReactNode;
  what?: string;
}) {
  if (q.isPending) {
    return (
      <div aria-busy="true" className="jobs-grid">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">Could not load {what}.</span>
        <Button size="sm" variant="outline" loading={q.isFetching} onClick={() => void q.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  return <>{children(q.data)}</>;
}

export function SectionHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      <div className="flex items-center gap-3">
        {children}
      </div>
    </div>
  );
}

/** Small thumbnails of the photos taken for a job; each opens the full picture. */
export function PhotoStrip({ photos }: { photos: Job["photos"] }) {
  if (!photos.length) return null;
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  return (
    <div className="photo-strip">
      {photos.map((p) => {
        const url = p.url.startsWith("/") ? `${base}${p.url}` : p.url;
        return (
          <a key={p.id} href={url} target="_blank" rel="noreferrer">
            <img src={url} alt={`${p.kind} photo`} loading="lazy" />
            <small>
              {p.kind}
              {p.weight_kg ? ` ${p.weight_kg} kg` : ""}
            </small>
          </a>
        );
      })}
    </div>
  );
}
