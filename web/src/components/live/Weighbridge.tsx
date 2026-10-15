import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, Scale, XCircle } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, PAYOUTS_KEY, STATS_KEY } from "@/api/hooks";
import { uploadPhoto, PhotoError } from "@/api/photos";
import { ApiError, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { useFormErrors } from "@/lib/useFormErrors";
import { LIMITS, PHOTO_TYPES, validatePhotoFile, validateWeightKg } from "@/lib/validation";
import { PhotoStrip, type Job } from "./common";

type GradeOut = components["schemas"]["GradeOut"];

const MOISTURE = { dry: "Dry", medium: "Medium moisture", wet: "Wet" } as const;

/** Loads that arrived: look at the photos, optionally ask for an AI estimate, then confirm the
 * weighbridge weight or reject the lot. */
export function Weighbridge({ jobs, canAct }: { jobs: Job[]; canAct: boolean }) {
  const [confirming, setConfirming] = useState<Job | null>(null);
  const [rejecting, setRejecting] = useState<Job | null>(null);
  return (
    <>
      <div className="jobs-grid">
        {jobs.map((job) => (
          <WeighCard key={job.id} job={job} canAct={canAct} onConfirm={setConfirming} onReject={setRejecting} />
        ))}
        {!jobs.length && <div className="empty-state">No load is waiting at the weighbridge.</div>}
      </div>
      {confirming && <ConfirmDialog job={confirming} onClose={() => setConfirming(null)} />}
      {rejecting && <RejectDialog job={rejecting} onClose={() => setRejecting(null)} />}
    </>
  );
}

function WeighCard({
  job,
  canAct,
  onConfirm,
  onReject,
}: {
  job: Job;
  canAct: boolean;
  onConfirm: (j: Job) => void;
  onReject: (j: Job) => void;
}) {
  const toast = useToast();
  const [grade, setGrade] = useState<GradeOut | null>(null);
  const [weighbridgePhoto, setWeighbridgePhoto] = useState<File | null>(null);
  const [photoProblem, setPhotoProblem] = useState("");
  const delivered = job.photos.find((p) => p.kind === "delivery")?.weight_kg;

  const estimate = useMutation({
    meta: { silent: true },
    mutationFn: async () => {
      let path: string | undefined;
      if (weighbridgePhoto) path = await uploadPhoto(job.id, "weighbridge", weighbridgePhoto);
      return unwrap(
        api.POST("/api/jobs/{job_id}/grade", { params: { path: { job_id: job.id } }, body: { photo_path: path } }),
      );
    },
    onSuccess: setGrade,
    onError: (e) => {
      if (e instanceof PhotoError) setPhotoProblem(e.message);
      toast.error(
        e instanceof ApiError && e.status === 503
          ? "The photo estimate is not set up on this server. You can still confirm the weight."
          : e instanceof Error
            ? e.message
            : "Could not estimate the grade.",
      );
    },
  });

  return (
    <article className="job-card">
      <span className="status-badge">
        <span />
        At the weighbridge
      </span>
      <h3 className="mt-4">
        {job.quantity_tonnes} t <span className="text-muted-foreground font-normal">· {job.residue_type}</span>
      </h3>
      <div className="job-details">
        <p>
          <Scale />
          {delivered ? `The transporter reports ${delivered} kg` : `Estimated ${job.est_weight_kg} kg`}
        </p>
        {job.transporter_name && <p>Delivered by {job.transporter_name}</p>}
      </div>
      <PhotoStrip photos={job.photos} />
      {grade && (
        <div className="job-details" role="status">
          <p>
            <CheckCircle2 />
            {MOISTURE[grade.grade.moisture_band]}, {Math.round(grade.grade.confidence * 100)}% sure
            {grade.grade.contamination_flags?.length ? `, flags: ${grade.grade.contamination_flags.join(", ")}` : ""}
          </p>
          <p className="table-sub">{grade.grade.disclaimer}</p>
        </div>
      )}
      {canAct ? (
        <>
          <Field label="Weighbridge photo (optional, for the estimate)" error={photoProblem} hint="JPEG, PNG or WebP, up to 5 MB">
            <input
              type="file"
              accept={PHOTO_TYPES.join(",")}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setWeighbridgePhoto(f);
                setPhotoProblem(f ? (validatePhotoFile(f) ?? "") : "");
              }}
            />
          </Field>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="outline" loading={estimate.isPending} disabled={Boolean(photoProblem)} onClick={() => estimate.mutate()}>
              <Camera />
              Estimate grade
            </Button>
            <Button onClick={() => onConfirm(job)}>
              <Scale />
              Confirm weight
            </Button>
            <Button variant="outline" onClick={() => onReject(job)}>
              <XCircle />
              Reject lot
            </Button>
          </div>
        </>
      ) : (
        <p className="auth-note mt-3">Only the factory can confirm the weight.</p>
      )}
    </article>
  );
}

function useAfterDecision() {
  const qc = useQueryClient();
  return () => {
    for (const key of [JOBS_KEY, PAYOUTS_KEY, STATS_KEY]) void qc.invalidateQueries({ queryKey: key });
  };
}

function ConfirmDialog({ job, onClose }: { job: Job; onClose: () => void }) {
  const toast = useToast();
  const form = useFormErrors();
  const settle = useAfterDecision();
  const [weight, setWeight] = useState(String(job.photos.find((p) => p.kind === "delivery")?.weight_kg ?? job.est_weight_kg));
  const confirm = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      unwrap(
        api.POST("/api/jobs/{job_id}/confirm", {
          params: { path: { job_id: job.id } },
          body: { accept: true, final_weight_kg: Number(weight), reason: "" },
        }),
      ),
    onSuccess: () => {
      toast.info("Weight confirmed. The farmer is asked to confirm the payment next.");
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not confirm the weight.");
    },
    onSettled: settle,
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    const bad = validateWeightKg(weight);
    if (bad) {
      form.fail({ final_weight_kg: bad });
      toast.error(bad);
      return;
    }
    form.reset();
    confirm.mutate();
  }
  return (
    <Dialog open onOpenChange={(open) => !open && !confirm.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Confirm the weighbridge weight</DialogTitle>
        <DialogDescription>
          {job.quantity_tonnes} t {job.residue_type}. Escrow of {pkr(job.escrow_amount)} is topped up or refunded to match.
        </DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} aria-busy={confirm.isPending}>
          <fieldset disabled={confirm.isPending} className="bare-fieldset auth-stack">
            <Field label="Weight on the weighbridge (kg)" error={form.errors.final_weight_kg} hint={`Estimated ${job.est_weight_kg} kg`}>
              <input
                inputMode="numeric"
                maxLength={LIMITS.weightText.max}
                value={weight}
                onChange={(e) => {
                  setWeight(e.target.value);
                  form.clear("final_weight_kg");
                }}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={confirm.isPending}>
                Confirm weight
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RejectDialog({ job, onClose }: { job: Job; onClose: () => void }) {
  const toast = useToast();
  const form = useFormErrors();
  const settle = useAfterDecision();
  const [reason, setReason] = useState("");
  const reject = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      unwrap(
        api.POST("/api/jobs/{job_id}/confirm", {
          params: { path: { job_id: job.id } },
          body: { accept: false, reason: reason.trim() },
        }),
      ),
    onSuccess: () => {
      toast.info("Lot rejected. The transporter is paid their share and the rest of the escrow is refunded.");
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not reject the lot.");
    },
    onSettled: settle,
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    const r = reason.trim();
    const bad = r.length < 3 ? "Give a reason of at least 3 characters" : r.length > 500 ? "Reason must be at most 500 characters" : "";
    if (bad) {
      form.fail({ reason: bad });
      toast.error(bad);
      return;
    }
    form.reset();
    reject.mutate();
  }
  return (
    <Dialog open onOpenChange={(open) => !open && !reject.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Reject this lot</DialogTitle>
        <DialogDescription>
          The farmer gets nothing. The transporter is paid their share; the rest of the escrow is refunded to you.
        </DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} aria-busy={reject.isPending}>
          <fieldset disabled={reject.isPending} className="bare-fieldset auth-stack">
            <Field label="Reason" error={form.errors.reason} hint="3 to 500 characters">
              <input
                value={reason}
                maxLength={500}
                onChange={(e) => {
                  setReason(e.target.value);
                  form.clear("reason");
                }}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={reject.isPending}>
                Reject lot
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}
