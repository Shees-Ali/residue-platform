import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Scale, ThumbsDown } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, LOTS_KEY, PAYOUTS_KEY, useJobs, useMyPayouts } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import { pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { useFormErrors } from "@/lib/useFormErrors";
import { QueryBoundary, SectionHead, STATE_LABEL, type Job } from "./common";

/** Jobs the factory has weighed: the farmer says yes (and is paid) or disputes. */
export function ConfirmSection() {
  const jobs = useJobs("confirmed");
  const [disputing, setDisputing] = useState<Job | null>(null);
  const verify = useVerify();
  return (
    <QueryBoundary q={jobs} what="your confirmations">
      {(waiting) =>
        waiting.length === 0 ? null : (
          <>
            <SectionHead title="Confirm your weight and payment" />
            <div className="jobs-grid">
              {waiting.map((job) => (
                <article className="job-card" key={job.id}>
                  <span className="status-badge">
                    <span />
                    Waiting for you
                  </span>
                  <h3 className="mt-4">
                    {job.quantity_tonnes} t <span className="text-muted-foreground font-normal">· {job.residue_type}</span>
                  </h3>
                  <div className="job-details">
                    <p>
                      <Scale />
                      {job.factory_name} weighed {job.final_weight_kg} kg (you reported {job.est_weight_kg} kg)
                    </p>
                    <p>
                      <CheckCircle2 />
                      You will be paid <strong className="text-primary">{pkr(job.est_farmer_payout)}</strong>
                    </p>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button
                      loading={verify.isPending && verify.variables?.job.id === job.id && verify.variables.confirmed}
                      disabled={verify.isPending}
                      onClick={() => verify.mutate({ job, confirmed: true, note: "" })}
                    >
                      Yes, pay me
                    </Button>
                    <Button variant="outline" disabled={verify.isPending} onClick={() => setDisputing(job)}>
                      <ThumbsDown />
                      Dispute
                    </Button>
                  </div>
                </article>
              ))}
            </div>
            {disputing && <DisputeDialog job={disputing} onClose={() => setDisputing(null)} />}
          </>
        )
      }
    </QueryBoundary>
  );
}

function useVerify() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ job, confirmed, note }: { job: Job; confirmed: boolean; note: string }) =>
      unwrap(
        api.POST("/api/jobs/{job_id}/verify", {
          params: { path: { job_id: job.id } },
          body: { confirmed, note },
        }),
      ),
    onSuccess: (r) =>
      toast.info(
        r.state === "settled"
          ? `Confirmed. ${pkr(r.farmer_amount ?? 0)} has been released to you.`
          : "Dispute sent. The money stays frozen until an admin looks into it.",
      ),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not send your answer."),
    onSettled: () => {
      for (const key of [JOBS_KEY, LOTS_KEY, PAYOUTS_KEY]) void qc.invalidateQueries({ queryKey: key });
    },
  });
}

function DisputeDialog({ job, onClose }: { job: Job; onClose: () => void }) {
  const form = useFormErrors();
  const toast = useToast();
  const [note, setNote] = useState("");
  const qc = useQueryClient();
  const send = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      unwrap(
        api.POST("/api/jobs/{job_id}/verify", {
          params: { path: { job_id: job.id } },
          body: { confirmed: false, note: note.trim() },
        }),
      ),
    onSuccess: () => {
      toast.info("Dispute sent. The money stays frozen until an admin looks into it.");
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not send your dispute.");
    },
    onSettled: () => {
      for (const key of [JOBS_KEY, LOTS_KEY, PAYOUTS_KEY]) void qc.invalidateQueries({ queryKey: key });
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    const n = note.trim();
    const bad =
      n.length < 3 ? "Tell us what is wrong (at least 3 characters)" : n.length > 1000 ? "Note must be at most 1000 characters" : "";
    if (bad) {
      form.fail({ note: bad });
      toast.error(bad);
      return;
    }
    form.reset();
    send.mutate();
  }
  return (
    <Dialog open onOpenChange={(open) => !open && !send.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Dispute the weight or payment</DialogTitle>
        <DialogDescription>
          {STATE_LABEL[job.state]}: {job.factory_name} weighed {job.final_weight_kg} kg. Nothing is paid until an admin
          resolves this.
        </DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} aria-busy={send.isPending}>
          <fieldset disabled={send.isPending} className="bare-fieldset auth-stack">
            <Field label="What is wrong?" error={form.errors.note} hint="3 to 1000 characters">
              <input
                value={note}
                maxLength={1000}
                onChange={(e) => {
                  setNote(e.target.value);
                  form.clear("note");
                }}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={send.isPending}>
                Send dispute
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** What the farmer has been paid, and what is still to come. */
export function Payments() {
  const payouts = useMyPayouts();
  return (
    <QueryBoundary q={payouts} what="your payments">
      {(rows) =>
        rows.length === 0 ? null : (
          <>
            <SectionHead title="Your payments" />
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.job_id}>
                      <td className="font-medium">{p.job_id.slice(0, 8)}</td>
                      <td>{STATE_LABEL[p.state] ?? p.state}</td>
                      <td>{p.status === "released" ? "Paid" : "Expected"}</td>
                      <td>{pkr(p.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      }
    </QueryBoundary>
  );
}
