import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Factory as FactoryIcon, MapPin, Truck, Wallet } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, OFFERS_KEY, PAYOUTS_KEY, useJobs, useMyPayouts, useOffers } from "@/api/hooks";
import { apiErrorFrom, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { PageHeading, Stat, pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { haversineKm } from "@/lib/domain/assignment";
import { useLocationTracker } from "@/lib/useLocationTracker";
import { LegDialog } from "./LegDialog";
import { MyDetailsLink } from "./MyDetailsLink";
import { JobStages, PhotoStrip, QueryBoundary, SectionHead, mmss, secondsLeft, useNow, type Job } from "./common";

type Offer = components["schemas"]["OfferOut"];

/** The transporter's page: offers with a countdown, then the jobs they have accepted. */
export function TransporterHome() {
  const offers = useOffers();
  const jobs = useJobs();
  const payouts = useMyPayouts();
  const now = useNow();
  const [leg, setLeg] = useState<{ job: Job; kind: "pickup" | "delivery" } | null>(null);

  const open = (all: Offer[]) =>
    all.filter((o) => o.status === "pending" && new Date(o.expires_at).getTime() > now);
  const paidFor = new Map((payouts.data ?? []).map((p) => [p.job_id, p]));

  return (
    <>
      <PageHeading
        eyebrow="TRANSPORTER DASHBOARD"
        title="Move harvests forward."
        description="Take a nearby load before the clock runs out, then record the pickup and the delivery."
        action={<MyDetailsLink />}
      />
      <QueryBoundary q={offers} what="your offers">
        {(all) => (
          <>
            <div className="stats-grid three">
              <Stat live label="Offers for you" value={open(all).length} icon={Truck} note="Waiting for your answer" tone="gold" />
              <Stat
                live
                label="Active jobs"
                value={(jobs.data ?? []).filter((j) => ["accepted", "picked_up"].includes(j.state)).length}
                icon={MapPin}
                note="Accepted and moving"
              />
              <Stat
                live
                label="Paid out"
                value={pkr((payouts.data ?? []).filter((p) => p.status === "released").reduce((n, p) => n + p.amount, 0))}
                icon={Wallet}
                note="Released after the factory confirms"
              />
            </div>

            <SectionHead title="Offers for you" />
            <div className="jobs-grid">
              {open(all).map((offer) => (
                <OfferCard key={offer.id} offer={offer} now={now} />
              ))}
              {!open(all).length && (
                <div className="empty-state">No offers right now. New ones appear here as factories fund loads.</div>
              )}
            </div>
          </>
        )}
      </QueryBoundary>

      <SectionHead title="My jobs" />
      <QueryBoundary q={jobs} what="your jobs">
        {(all) => (
          <div className="jobs-grid">
            {all.map((job) => {
              const pay = paidFor.get(job.id);
              return (
                <article className="job-card" key={job.id}>
                  <div className="flex items-center justify-between">
                    <span className="status-badge">
                      <span />
                      {pay?.status === "released" ? "Paid" : "Payout pending"}
                    </span>
                    <span className="text-xs text-muted-foreground">{job.factory_name}</span>
                  </div>
                  <h3 className="mt-4">
                    {job.quantity_tonnes} t <span className="text-muted-foreground font-normal">· {job.residue_type}</span>
                  </h3>
                  <div className="job-details">
                    <p>
                      <MapPin />
                      Pickup: {job.village}
                      {job.district ? `, ${job.district}` : ""}
                    </p>
                    <p>
                      <FactoryIcon />
                      Deliver to {job.factory_name}
                    </p>
                    {job.farmer_phone && (
                      <p>
                        <Truck />
                        Farmer: {job.farmer_name ?? "Unnamed"} · {job.farmer_phone}
                      </p>
                    )}
                  </div>
                  <p className="text-sm">
                    {pay?.status === "released" ? "Paid" : "You will be paid about"}{" "}
                    <strong className="text-primary">{pkr(pay?.amount ?? job.est_transporter_payout)}</strong>
                  </p>
                  <PhotoStrip photos={job.photos} />
                  <JobStages state={job.state} />
                  {job.state === "accepted" && (
                    <Button className="mt-3" onClick={() => setLeg({ job, kind: "pickup" })}>
                      <Camera />
                      Record pickup
                    </Button>
                  )}
                  {job.state === "picked_up" && (
                    <Button className="mt-3" onClick={() => setLeg({ job, kind: "delivery" })}>
                      <Camera />
                      Record delivery
                    </Button>
                  )}
                  <ShareLocation job={job} />
                </article>
              );
            })}
            {!all.length && <div className="empty-state">Accepted jobs show up here.</div>}
          </div>
        )}
      </QueryBoundary>
      {leg && <LegDialog job={leg.job} kind={leg.kind} onClose={() => setLeg(null)} />}
    </>
  );
}

/** While a job is accepted or on the road, send this phone's position so the factory can follow. */
function ShareLocation({ job }: { job: Job }) {
  const { status, problem } = useLocationTracker(job.id, job.state === "accepted" || job.state === "picked_up");
  if (status === "off") return null;
  return (
    <p className={`chip mt-3 ${status === "sharing" ? "" : "warn"}`} role="status">
      {status === "sharing"
        ? "Sharing your location"
        : status === "blocked"
          ? "Location is blocked. Allow it in your browser so the factory can follow the load."
          : problem || "Finding your location…"}
    </p>
  );
}

function OfferCard({ offer, now }: { offer: Offer; now: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const left = secondsLeft(offer.expires_at, now);
  const km = haversineKm(offer.pickup_lat, offer.pickup_lon, offer.factory_lat, offer.factory_lon);
  const refresh = () => {
    for (const key of [OFFERS_KEY, JOBS_KEY, PAYOUTS_KEY]) void qc.invalidateQueries({ queryKey: key });
  };
  const accept = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/offers/{offer_id}/accept", { params: { path: { offer_id: offer.id } } })),
    onSuccess: () => toast.info("Job accepted. Record the pickup when you reach the farm."),
    onSettled: refresh, // a 409 (someone else won, or it lapsed) is toasted by the shared handler
  });
  const decline = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/offers/{offer_id}/decline", {
        params: { path: { offer_id: offer.id } },
      });
      if (error !== undefined) throw apiErrorFrom(error, response.status);
    },
    onSuccess: () => toast.info("Passed. The load goes to the next transporter."),
    onSettled: refresh,
  });
  const busy = accept.isPending || decline.isPending;
  return (
    <article className="job-card">
      <div className="flex items-center justify-between">
        <span className="countdown" aria-label="Time left to answer">{left > 0 ? mmss(left) : "Lapsed"}</span>
        <span className="text-xs text-muted-foreground">{offer.factory_name}</span>
      </div>
      <h3 className="mt-4">
        {(offer.est_weight_kg / 1000).toFixed(1)} t <span className="text-muted-foreground font-normal">· {offer.residue_type}</span>
      </h3>
      <div className="job-details">
        <p>
          <MapPin />
          Pickup: {offer.village ?? "see map"}
        </p>
        <p>
          <FactoryIcon />
          {km.toFixed(1)} km to {offer.factory_name}
        </p>
      </div>
      <p className="text-sm">
        Your pay about <strong className="text-primary">{pkr(offer.payout_amount)}</strong>
      </p>
      <div className="mt-3 flex gap-2">
        <Button loading={accept.isPending} disabled={busy || left === 0} onClick={() => accept.mutate()}>
          Accept job
        </Button>
        <Button variant="outline" loading={decline.isPending} disabled={busy || left === 0} onClick={() => decline.mutate()}>
          Pass
        </Button>
      </div>
    </article>
  );
}
