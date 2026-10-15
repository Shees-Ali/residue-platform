import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight, Leaf, Megaphone, ShieldAlert } from "lucide-react";
import { api } from "@/api/client";
import { ESCALATIONS_KEY, JOBS_KEY, STATS_KEY, useEscalations, useImpact, useJobLedger, useLedger, useLedgerCheck } from "@/api/hooks";
import { apiErrorFrom } from "@/api/query";
import { pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { QueryBoundary, SectionHead, when } from "./common";

export const KIND_LABEL: Record<string, string> = {
  escrow_in: "Escrow in",
  release_farmer: "Paid to farmer",
  release_transporter: "Paid to transporter",
  platform_fee: "Platform fee",
  refund: "Refunded to factory",
  release_factory: "Sale: factory share",
  release_ngo: "Sale: NGO share",
};

const PAGE = 15;

/** Does the money add up? Escrow in must equal what was paid out, kept and refunded. */
export function LedgerCheckBadge() {
  const check = useLedgerCheck();
  if (check.isPending) return <Skeleton className="h-6 w-40" />;
  if (check.isError) return <span className="chip warn">Could not run the ledger check</span>;
  const c = check.data;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`chip ${c.balanced ? "" : "warn"}`} role="status">
        {c.balanced ? <CheckCircle2 size={13} /> : <ShieldAlert size={13} />}
        {c.balanced ? "Ledger balanced" : `Ledger out of balance (${c.unbalanced_jobs.length + c.unbalanced_orders.length})`}
      </span>
      <span className="chip">{c.jobs_checked} jobs and {c.orders_checked} orders checked</span>
      <span className="chip warn">Held in escrow {pkr(c.held_in_escrow)}</span>
    </div>
  );
}

/** Admin: every money movement, newest first, with the invariant check on top. */
export function AdminLedger() {
  const [offset, setOffset] = useState(0);
  const ledger = useLedger(offset, PAGE);
  return (
    <section aria-label="Ledger" className="mb-8">
      <SectionHead title="Ledger and escrow check" />
      <LedgerCheckBadge />
      <div className="mt-3">
        <QueryBoundary q={ledger} what="the ledger">
          {(rows) => (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>What</th>
                      <th>For</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((e) => (
                      <tr key={e.id}>
                        <td>{when(e.created_at)}</td>
                        <td>{KIND_LABEL[e.kind] ?? e.kind}</td>
                        <td>
                          {e.job_id ? `Job ${e.job_id.slice(0, 8)}` : `Order ${(e.order_id ?? "").slice(0, 8)}`}
                        </td>
                        <td>{pkr(e.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!rows.length && <p className="p-8 text-center text-muted-foreground">No money has moved yet.</p>}
              </div>
              <div className="mt-2 flex items-center justify-end gap-2">
                <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                  <ChevronLeft />
                  Newer
                </Button>
                <Button size="sm" variant="outline" disabled={rows.length < PAGE || ledger.isPlaceholderData} onClick={() => setOffset(offset + PAGE)}>
                  Older
                  <ChevronRight />
                </Button>
              </div>
            </>
          )}
        </QueryBoundary>
      </div>
    </section>
  );
}

/** Admin: how much residue has been kept out of burning, with the traceable records. */
export function ImpactPanel() {
  const impact = useImpact();
  return (
    <section aria-label="Impact" className="mb-8">
      <SectionHead title="Residue kept from burning" />
      <QueryBoundary q={impact} what="the impact numbers">
        {(i) => (
          <>
            <p className="text-sm">
              <Leaf className="inline" size={16} /> <strong>{i.tonnes_diverted.toFixed(1)} tonnes</strong> from {i.jobs_settled} settled
              jobs.
            </p>
            {i.records.length > 0 && (
              <div className="table-wrap mt-3">
                <table>
                  <thead>
                    <tr>
                      <th>Farmer</th>
                      <th>Place</th>
                      <th>Weight</th>
                      <th>Settled</th>
                    </tr>
                  </thead>
                  <tbody>
                    {i.records.map((r) => (
                      <tr key={r.job_id}>
                        <td className="font-medium">{r.farmer_name}</td>
                        <td>
                          {r.village}
                          <span className="table-sub">{r.district}</span>
                        </td>
                        <td>{r.weight_kg} kg</td>
                        <td>{when(r.settled_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </QueryBoundary>
    </section>
  );
}

/** Admin: farmers who asked for a person and disputes, until someone answers them. */
export function EscalationQueue() {
  const queue = useEscalations();
  const qc = useQueryClient();
  const toast = useToast();
  const resolve = useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.POST("/api/escalations/{escalation_id}/resolve", {
        params: { path: { escalation_id: id } },
      });
      if (error !== undefined) throw apiErrorFrom(error, response.status);
    },
    onSuccess: () => toast.info("Marked as resolved."),
    onSettled: () => {
      for (const key of [ESCALATIONS_KEY, STATS_KEY, JOBS_KEY]) void qc.invalidateQueries({ queryKey: key });
    },
  });
  return (
    <section aria-label="Escalations" className="mb-8">
      <SectionHead title="Needs a person" />
      <QueryBoundary q={queue} what="the queue">
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">Nothing needs a person right now.</div>
          ) : (
            <div className="activity-list">
              {rows.map((e) => (
                <div key={e.id}>
                  <span className="activity-icon">
                    <Megaphone size={15} />
                  </span>
                  <div className="flex-1">
                    <p>{e.summary}</p>
                    <small>
                      {e.farmer_phone ?? "Unknown caller"} · {when(e.created_at)} · {e.job_id ? "web dispute" : "phone call"}
                    </small>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={resolve.isPending && resolve.variables === e.id}
                    disabled={resolve.isPending}
                    onClick={() => resolve.mutate(e.id)}
                  >
                    Resolve
                  </Button>
                </div>
              ))}
            </div>
          )
        }
      </QueryBoundary>
    </section>
  );
}

/** One job's money: what went in, what went out. For the factory and the admin. */
export function JobMoneyDialog({ jobId, title, onClose }: { jobId: string; title: string; onClose: () => void }) {
  const entries = useJobLedger(jobId);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Money for this load</DialogTitle>
        <DialogDescription>{title}</DialogDescription>
        {entries.isPending ? (
          <Skeleton className="h-24" />
        ) : entries.isError ? (
          <Button variant="outline" onClick={() => void entries.refetch()}>
            Try again
          </Button>
        ) : entries.data.length === 0 ? (
          <p className="auth-note">No money has moved for this load yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>What</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {entries.data.map((e) => (
                  <tr key={e.id}>
                    <td>{when(e.created_at)}</td>
                    <td>{KIND_LABEL[e.kind] ?? e.kind}</td>
                    <td>{pkr(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

