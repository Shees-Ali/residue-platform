import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Factory as FactoryIcon, MapPin } from "lucide-react";
import { api } from "@/api/client";
import { LOTS_KEY, useLots } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { JOB_STATE_LABEL, pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { useFormErrors } from "@/lib/useFormErrors";
import { JobActivityButton } from "./JobActivity";
import { LotEditDialog, canEditLot } from "./LotEditDialog";
import type { JobState } from "@/lib/domain/types";

export type Lot = components["schemas"]["LotOut"];

export const LiveLabel = () => (
  <span className="demo-label live">
    <span />
    Live data
  </span>
);

/** Where a lot is in its life, in words a farmer or an admin understands. */
export function stageOf(lot: Lot): string {
  if (!lot.job_id) return lot.status === "rejected" ? "Rejected" : "Waiting for a factory";
  return JOB_STATE_LABEL[lot.job_state as JobState] ?? lot.job_state ?? "In progress";
}

const day = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "";

/** Shows the loading skeleton, the retry state or the children, so every list handles all three. */
function Async({ q, children }: { q: ReturnType<typeof useLots>; children: (lots: Lot[]) => React.ReactNode }) {
  if (q.isPending) {
    return (
      <div aria-busy="true" className="jobs-grid">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">Could not load the lots.</span>
        <Button size="sm" variant="outline" loading={q.isFetching} onClick={() => void q.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  return <>{children(q.data)}</>;
}

/** A farmer's own requests, with where each one stands and what they are expected to receive. */
export function MyRequests() {
  const lots = useLots();
  return (
    <Async q={lots}>
      {(rows) =>
        rows.length === 0 ? (
          <div className="empty-state">No requests yet. Report your first residue collection above.</div>
        ) : (
          <div className="jobs-grid">
            {rows.map((lot) => (
              <article className="job-card" key={lot.id}>
                <div className="flex items-center justify-between">
                  <span className="status-badge">
                    <span />
                    {stageOf(lot)}
                  </span>
                  <span className="text-xs text-muted-foreground">{day(lot.created_at)}</span>
                </div>
                <h3 className="mt-4">
                  {lot.quantity_tonnes} t{" "}
                  <span className="text-muted-foreground font-normal">· {lot.residue_label ?? lot.residue_type}</span>
                </h3>
                <div className="job-details">
                  <p>
                    <MapPin />
                    {lot.village}, {lot.district}
                    {lot.place_match === "district" && " (district centre used)"}
                  </p>
                  <p>
                    <FactoryIcon />
                    {lot.factory_name ?? "Matching factories…"}
                  </p>
                  <p>
                    <CalendarDays />
                    {day(lot.pickup_from)}
                  </p>
                </div>
                {lot.est_farmer_payout != null && (
                  <p className="text-sm">
                    You would receive about <strong>{pkr(lot.est_farmer_payout)}</strong>
                    <span className="table-sub">An estimate until the factory weighs the load.</span>
                  </p>
                )}
              </article>
            ))}
          </div>
        )
      }
    </Async>
  );
}

/** Every lot, for the admin: who reported it, where, which factory it went to. */
export function AdminLots() {
  const lots = useLots();
  const [ranked, setRanked] = useState<Lot | null>(null);
  const [editing, setEditing] = useState<Lot | null>(null);
  return (
    <>
      <Async q={lots}>
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">No lots yet. Add one for a farmer, or wait for a call.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Farmer</th>
                    <th>Residue</th>
                    <th>Place</th>
                    <th>Pickup</th>
                    <th>Factory</th>
                    <th>Stage</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((lot) => (
                    <tr key={lot.id}>
                      <td className="font-medium">
                        {lot.farmer_name ?? "Unnamed farmer"}
                        <span className="table-sub">{lot.farmer_phone}</span>
                      </td>
                      <td>
                        {lot.quantity_tonnes} t {lot.residue_label ?? lot.residue_type}
                      </td>
                      <td>
                        {lot.village}
                        <span className="table-sub">
                          {lot.district}
                          {lot.place_match === "district" && " · district centre"}
                        </span>
                      </td>
                      <td>{day(lot.pickup_from)}</td>
                      <td>{lot.factory_name ?? "None yet"}</td>
                      <td>
                        <span className="status-badge">
                          <span />
                          {stageOf(lot)}
                        </span>
                      </td>
                      <td>
                        <Button size="sm" variant="ghost" onClick={() => setRanked(lot)} disabled={!lot.job_id}>
                          Ranking
                        </Button>
                        {lot.job_id && (
                          <JobActivityButton
                            jobId={lot.job_id}
                            title={`${lot.quantity_tonnes} t ${lot.residue_label ?? lot.residue_type} from ${lot.village}`}
                          />
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditing(lot)}
                          disabled={!canEditLot(lot)}
                          title={canEditLot(lot) ? undefined : "Locked after funding"}
                          aria-label={`Edit lot of ${lot.farmer_name ?? "a farmer"}`}
                        >
                          {canEditLot(lot) ? "Edit" : "Locked"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </Async>
      {ranked && <RankingDialog lot={ranked} onClose={() => setRanked(null)} />}
      {editing && <LotEditDialog lot={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

/** The ranked factories for a lot, and a logged override while the job is not yet funded. */
function RankingDialog({ lot, onClose }: { lot: Lot; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const form = useFormErrors();
  const [factoryId, setFactoryId] = useState("");
  const [reason, setReason] = useState("");
  const ranking = useQuery({
    queryKey: ["ranking", lot.id],
    queryFn: () => unwrap(api.GET("/api/lots/{lot_id}/ranking", { params: { path: { lot_id: lot.id } } })),
  });
  const canOverride = lot.job_state === "created";

  const override = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      unwrap(
        api.POST("/api/lots/{lot_id}/override", {
          params: { path: { lot_id: lot.id } },
          body: { factory_id: factoryId, reason: reason.trim() },
        }),
      ),
    onSuccess: () => {
      toast.info("Factory changed. The reason is logged.");
      void qc.invalidateQueries({ queryKey: LOTS_KEY });
      void qc.invalidateQueries({ queryKey: ["ranking", lot.id] });
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not change the factory.");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors: Record<string, string> = {};
    if (!factoryId) errors.factory_id = "Choose the factory to assign";
    const r = reason.trim();
    if (r.length < 3) errors.reason = r ? "Reason must be at least 3 characters" : "Give a reason, at least 3 characters";
    if (r.length > 500) errors.reason = "Reason must be at most 500 characters";
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(Object.values(errors).join("; "));
      return;
    }
    form.reset();
    override.mutate();
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Factory ranking</DialogTitle>
        <DialogDescription>
          {lot.quantity_tonnes} t {lot.residue_label} from {lot.village}, {lot.district}
        </DialogDescription>
        {ranking.isPending ? (
          <Skeleton className="h-32" />
        ) : ranking.isError ? (
          <Button variant="outline" onClick={() => void ranking.refetch()}>
            Try again
          </Button>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Factory</th>
                  <th>Distance</th>
                  <th>Price / t</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {ranking.data.map((r) => (
                  <tr key={r.factory_id}>
                    <td className="font-medium">
                      {r.rank}
                      {r.chosen && <span className="table-sub">assigned</span>}
                    </td>
                    <td>
                      {r.factory_name}
                      {r.override_reason && <span className="table-sub">Override: {r.override_reason}</span>}
                    </td>
                    <td>{r.distance_km.toFixed(1)} km</td>
                    <td>{pkr(r.price_per_tonne)}</td>
                    <td>{r.score.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {canOverride && ranking.data && (
          <form noValidate ref={form.ref} onSubmit={submit} className="form-grid" aria-busy={override.isPending}>
            <fieldset disabled={override.isPending} className="bare-fieldset form-grid col-span-full">
              <Field label="Assign a different factory" error={form.errors.factory_id}>
                <select
                  value={factoryId}
                  onChange={(e) => {
                    setFactoryId(e.target.value);
                    form.clear("factory_id");
                  }}
                >
                  <option value="">Choose…</option>
                  {ranking.data
                    .filter((r) => !r.chosen)
                    .map((r) => (
                      <option key={r.factory_id} value={r.factory_id}>
                        {r.factory_name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Reason (logged)" error={form.errors.reason} hint="3 to 500 characters">
                <input
                  value={reason}
                  maxLength={500}
                  onChange={(e) => {
                    setReason(e.target.value);
                    form.clear("reason");
                  }}
                />
              </Field>
              <div className="col-span-full flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={onClose}>
                  Close
                </Button>
                <Button type="submit" loading={override.isPending}>
                  Override
                </Button>
              </div>
            </fieldset>
          </form>
        )}
        {!canOverride && (
          <p className="auth-note">The factory can only be changed before it funds the job.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
