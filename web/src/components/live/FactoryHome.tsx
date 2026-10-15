import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Factory as FactoryIcon, MapPin, Truck, Wallet } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, PAYOUTS_KEY, STATS_KEY, useJobs } from "@/api/hooks";
import { unwrap } from "@/api/query";
import { PageHeading, Stat, pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/auth/AuthProvider";
import { JobStages, PhotoStrip, QueryBoundary, SectionHead, STATE_LABEL, type Job } from "./common";
import { JobMoneyDialog } from "./AdminLedger";
import { FactoryOrders, FactoryProducts } from "./FactoryProducts";
import { TrackDialog } from "./TrackViews";
import { Weighbridge } from "./Weighbridge";

const MOVING = ["funded", "offered", "accepted", "picked_up", "confirmed"];
const FINISHED = ["settled", "rejected", "disputed"];

/** The factory's page: fund escrow for matched lots, then follow each load to settlement. */
export function FactoryHome() {
  const { user } = useAuth();
  const jobs = useJobs();
  const isFactory = user?.role === "factory";
  const [funding, setFunding] = useState<Job | null>(null);
  const [tracking, setTracking] = useState<Job | null>(null);
  const [money, setMoney] = useState<Job | null>(null);

  return (
    <>
      <PageHeading
        eyebrow="FACTORY DASHBOARD"
        title="From residue to resources."
        description="Fund the loads matched to you, then follow each one until it is weighed and paid."
      />
      <QueryBoundary q={jobs} what="your jobs">
        {(all) => {
          const waiting = all.filter((j) => j.state === "created");
          const moving = all.filter((j) => MOVING.includes(j.state));
          const stuck = all.filter((j) => j.offers_exhausted);
          const arrived = all.filter((j) => j.state === "delivered");
          const finished = all.filter((j) => FINISHED.includes(j.state));
          return (
            <>
              <div className="stats-grid three">
                <Stat live label="Awaiting escrow" value={waiting.length} icon={Wallet} note="Fund to start dispatch" tone="gold" />
                <Stat live label="On the road" value={moving.length} icon={Truck} note="Funded through weighing" />
                <Stat live label="Need a transporter" value={stuck.length} icon={FactoryIcon} note="Every transporter passed" />
              </div>

              <SectionHead title="Fund escrow to start dispatch" />
              <div className="jobs-grid">
                {waiting.map((job) => (
                  <JobCard key={job.id} job={job}>
                    <p className="text-sm">
                      Escrow to fund: <strong className="text-primary">{pkr(job.escrow_amount)}</strong>
                    </p>
                    {isFactory ? (
                      <Button className="mt-3" onClick={() => setFunding(job)}>
                        <Wallet />
                        Fund escrow
                      </Button>
                    ) : (
                      <p className="auth-note mt-3">Only the factory can fund this job.</p>
                    )}
                  </JobCard>
                ))}
                {!waiting.length && <div className="empty-state">Nothing is waiting for escrow.</div>}
              </div>

              <SectionHead title="At the weighbridge" />
              <Weighbridge jobs={arrived} canAct={isFactory} />

              <SectionHead title="Loads in progress" />
              <div className="jobs-grid">
                {moving.map((job) => (
                  <JobCard key={job.id} job={job}>
                    <JobStages state={job.state} />
                    <PhotoStrip photos={job.photos} />
                    {["accepted", "picked_up"].includes(job.state) && (
                      <Button className="mt-3" variant="outline" onClick={() => setTracking(job)}>
                        <MapPin />
                        Track this load
                      </Button>
                    )}
                    {job.state === "confirmed" && (
                      <p className="auth-note mt-3">Weight confirmed. Waiting for the farmer to confirm the payment.</p>
                    )}
                    <Button className="mt-3" variant="ghost" size="sm" onClick={() => setMoney(job)}>
                      <Wallet />
                      Money
                    </Button>
                    {job.offers_exhausted && (
                      <p className="auth-note">Every transporter passed. An admin can send it out again.</p>
                    )}
                  </JobCard>
                ))}
                {!moving.length && <div className="empty-state">No loads on the road yet.</div>}
              </div>

              <SectionHead title="Finished loads" />
              <div className="jobs-grid">
                {finished.map((job) => (
                  <JobCard key={job.id} job={job}>
                    <JobStages state={job.state} />
                    {job.rejection_reason && <p className="auth-note">Rejected: {job.rejection_reason}</p>}
                    <Button className="mt-3" variant="ghost" size="sm" onClick={() => setMoney(job)}>
                      <Wallet />
                      Money
                    </Button>
                  </JobCard>
                ))}
                {!finished.length && <div className="empty-state">Settled loads appear here.</div>}
              </div>

              <FactoryProducts canAct={isFactory} />
              <FactoryOrders />
            </>
          );
        }}
      </QueryBoundary>
      {funding && <FundDialog job={funding} onClose={() => setFunding(null)} />}
      {money && (
        <JobMoneyDialog
          jobId={money.id}
          title={`${money.quantity_tonnes} t ${money.residue_type} from ${money.village}`}
          onClose={() => setMoney(null)}
        />
      )}
      {tracking && (
        <TrackDialog
          jobId={tracking.id}
          title={`${tracking.quantity_tonnes} t ${tracking.residue_type} from ${tracking.village}`}
          onClose={() => setTracking(null)}
        />
      )}
    </>
  );
}

function JobCard({ job, children }: { job: Job; children?: React.ReactNode }) {
  return (
    <article className="job-card">
      <span className="status-badge">
        <span />
        {STATE_LABEL[job.state] ?? job.state}
      </span>
      <h3 className="mt-4">
        {job.quantity_tonnes} t <span className="text-muted-foreground font-normal">· {job.residue_type}</span>
      </h3>
      <div className="job-details">
        <p>
          <MapPin />
          {job.village}
          {job.district ? `, ${job.district}` : ""}
        </p>
        {job.transporter_name && (
          <p>
            <Truck />
            {job.transporter_name}
          </p>
        )}
      </div>
      {children}
    </article>
  );
}

function FundDialog({ job, onClose }: { job: Job; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const fund = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/jobs/{job_id}/fund", { params: { path: { job_id: job.id } } })),
    onSuccess: (done) => {
      toast.info(
        done.state === "offered"
          ? "Escrow funded. The nearest transporter has been offered the load."
          : "Escrow funded. No transporter is available yet; an admin can send it out again.",
      );
      onClose();
    },
    onSettled: () => {
      for (const key of [JOBS_KEY, PAYOUTS_KEY, STATS_KEY]) void qc.invalidateQueries({ queryKey: key });
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && !fund.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Fund escrow</DialogTitle>
        <DialogDescription>
          {job.quantity_tonnes} t {job.residue_type} from {job.village}. The money is held until the load is
          weighed and the farmer confirms.
        </DialogDescription>
        <div className="job-details">
          <p>
            <CheckCircle2 />
            Escrow: <strong>{pkr(job.escrow_amount)}</strong> ({job.est_weight_kg} kg at {pkr(job.quoted_price_per_tonne)} per tonne)
          </p>
          <p>
            <CheckCircle2 />
            Transporter share about {pkr(job.est_transporter_payout)}, farmer about {pkr(job.est_farmer_payout)}
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={fund.isPending}>
            Cancel
          </Button>
          <Button loading={fund.isPending} onClick={() => fund.mutate()}>
            Fund {pkr(job.escrow_amount)}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
