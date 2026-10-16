import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FastForward, RefreshCw } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, OFFERS_KEY, TRANSPORTERS_KEY, useJobs, usePoll, useTransporters } from "@/api/hooks";
import { unwrap } from "@/api/query";
import { pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { QueryBoundary, STATE_LABEL, SectionHead, when, type Job } from "./common";

/** Admin: the offer ladder for every job waiting on a transporter, and the transporter roster. */
export function AdminDispatch() {
  const jobs = useJobs();
  const toast = useToast();
  const qc = useQueryClient();
  const [ladderFor, setLadderFor] = useState<Job | null>(null);
  const refresh = () => {
    for (const key of [JOBS_KEY, OFFERS_KEY]) void qc.invalidateQueries({ queryKey: key });
  };

  const tick = useMutation({
    mutationFn: () => unwrap(api.POST("/api/dispatch/tick", { body: { force: true } })),
    onSuccess: (r) =>
      toast.info(
        r.expired === 0 && r.dispatched === 0
          ? "No offers were waiting."
          : `${r.expired} offer(s) moved on, ${r.reoffered} sent to the next transporter, ${r.exhausted} ran out of transporters.`,
      ),
    onSettled: refresh,
  });
  const redispatch = useMutation({
    mutationFn: (job: Job) =>
      unwrap(api.POST("/api/jobs/{job_id}/redispatch", { params: { path: { job_id: job.id } } })),
    onSuccess: () => toast.info("Offered to the next transporter."),
    onSettled: refresh,
  });

  return (
    <section aria-label="Dispatch" className="mb-8">
      <SectionHead title="Dispatch">
        <Button size="sm" variant="outline" loading={tick.isPending} onClick={() => tick.mutate()}>
          <FastForward />
          Move pending offers on now
        </Button>
      </SectionHead>
      <QueryBoundary q={jobs} what="the dispatch queue">
        {(all) => {
          const queue = all.filter((j) => j.state === "funded" || j.state === "offered");
          return queue.length === 0 ? (
            <div className="empty-state">No job is waiting on a transporter.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Load</th>
                    <th>Factory</th>
                    <th>Stage</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {queue.map((job) => (
                    <tr key={job.id}>
                      <td className="font-medium">
                        {job.quantity_tonnes} t {job.residue_type}
                        <span className="table-sub">{job.village}</span>
                      </td>
                      <td>{job.factory_name}</td>
                      <td>
                        <span className="status-badge">
                          <span />
                          {job.offers_exhausted ? "Every transporter passed" : STATE_LABEL[job.state]}
                        </span>
                      </td>
                      <td>
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="ghost" onClick={() => setLadderFor(job)}>
                            Offers
                          </Button>
                          {job.state === "funded" && (
                            <Button
                              size="sm"
                              variant="outline"
                              loading={redispatch.isPending && redispatch.variables?.id === job.id}
                              disabled={redispatch.isPending}
                              onClick={() => redispatch.mutate(job)}
                            >
                              <RefreshCw />
                              Send out again
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </QueryBoundary>
      <TransporterRoster />
      {ladderFor && <LadderDialog job={ladderFor} onClose={() => setLadderFor(null)} />}
    </section>
  );
}

function LadderDialog({ job, onClose }: { job: Job; onClose: () => void }) {
  const ladder = useQuery({
    queryKey: ["ladder", job.id],
    queryFn: () => unwrap(api.GET("/api/jobs/{job_id}/offers", { params: { path: { job_id: job.id } } })),
    refetchInterval: usePoll(4000),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Offers for this load</DialogTitle>
        <DialogDescription>
          {job.quantity_tonnes} t {job.residue_type} from {job.village}, one transporter at a time.
        </DialogDescription>
        {ladder.isPending ? (
          <Skeleton className="h-24" />
        ) : ladder.isError ? (
          <Button variant="outline" onClick={() => void ladder.refetch()}>
            Try again
          </Button>
        ) : ladder.data.length === 0 ? (
          <p className="auth-note">No transporter has been offered this load yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Transporter</th>
                  <th>Status</th>
                  <th>Expires</th>
                  <th>Pay</th>
                </tr>
              </thead>
              <tbody>
                {ladder.data.map((o) => (
                  <tr key={o.id}>
                    <td>{o.sequence}</td>
                    <td>
                      {o.transporter_name ?? "Transporter"}
                      <span className="table-sub">{o.transporter_phone}</span>
                    </td>
                    <td>{o.status}</td>
                    <td>{when(o.expires_at)}</td>
                    <td>{pkr(o.payout_amount)}</td>
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

function TransporterRoster() {
  const roster = useTransporters();
  const qc = useQueryClient();
  const toast = useToast();
  const change = useMutation({
    mutationFn: ({ id, revoke }: { id: string; revoke: boolean }) =>
      revoke
        ? unwrap(api.POST("/api/transporters/{transporter_id}/revoke", { params: { path: { transporter_id: id } } }))
        : unwrap(
            api.POST("/api/transporters/{transporter_id}/approve", {
              params: { path: { transporter_id: id } },
              body: { tier: 1 },
            }),
          ),
    onSuccess: (_t, v) => toast.info(v.revoke ? "Transporter stopped." : "Transporter approved at tier 1."),
    onSettled: () => void qc.invalidateQueries({ queryKey: TRANSPORTERS_KEY }),
  });
  return (
    <>
      <div className="section-title">
        <h2>Transporters</h2>
      </div>
      <QueryBoundary q={roster} what="the transporters">
        {(all) => (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Tier</th>
                  <th>Carries up to</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {all.map((t) => (
                  <tr key={t.id}>
                    <td className="font-medium">{t.display_name ?? "Unnamed"}</td>
                    <td>{t.phone}</td>
                    <td>{t.tier}</td>
                    <td>{t.max_tonnes} t</td>
                    <td>{t.approved ? "Approved" : "Not approved"}</td>
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={change.isPending && change.variables?.id === t.id}
                        disabled={change.isPending}
                        onClick={() => change.mutate({ id: t.id, revoke: t.approved })}
                      >
                        {t.approved ? "Stop offers" : "Approve"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryBoundary>
    </>
  );
}
