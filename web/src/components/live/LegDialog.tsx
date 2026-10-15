import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, MapPin } from "lucide-react";
import { api } from "@/api/client";
import { JOBS_KEY, PAYOUTS_KEY, TRACK_KEY } from "@/api/hooks";
import { uploadPhoto, PhotoError } from "@/api/photos";
import { ApiError, unwrap } from "@/api/query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { LocationError, getPosition } from "@/lib/geo";
import { useFormErrors } from "@/lib/useFormErrors";
import {
  PHOTO_TYPES,
  accuracyWarning,
  summarize,
  validatePhotoFile,
  validateWeightKg,
  weightWarning,
  type Errors,
  LIMITS,
} from "@/lib/validation";
import type { Job } from "./common";

const COPY = {
  pickup: {
    title: "Record pickup",
    blurb: "Photograph the load at the farm and enter the weight you loaded.",
    weightLabel: "Weight loaded (kg)",
    button: "Record pickup",
    done: "Pickup recorded. Drive to the factory.",
  },
  delivery: {
    title: "Record delivery",
    blurb: "Photograph the load at the factory gate and enter the weight you delivered.",
    weightLabel: "Weight delivered (kg)",
    button: "Record delivery",
    done: "Delivery recorded. The factory will weigh it next.",
  },
} as const;

/** Pickup or delivery: a photo, a weight and where the transporter is, sent in that order. */
export function LegDialog({
  job,
  kind,
  onClose,
}: {
  job: Job;
  kind: "pickup" | "delivery";
  onClose: () => void;
}) {
  const copy = COPY[kind];
  const toast = useToast();
  const qc = useQueryClient();
  const form = useFormErrors();
  const [file, setFile] = useState<File | null>(null);
  const [weight, setWeight] = useState(String(job.est_weight_kg));
  const [step, setStep] = useState("");
  const [accuracy, setAccuracy] = useState<string | undefined>();
  const preview = file && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "";

  const send = useMutation({
    meta: { silent: true }, // shown under the fields instead
    mutationFn: async () => {
      setStep("Getting your location…");
      const here = await getPosition();
      setAccuracy(accuracyWarning(here.accuracy_m));
      setStep("Uploading the photo…");
      const path = await uploadPhoto(job.id, kind, file as File);
      setStep("Saving…");
      return unwrap(
        api.POST(kind === "pickup" ? "/api/jobs/{job_id}/pickup" : "/api/jobs/{job_id}/deliver", {
          params: { path: { job_id: job.id } },
          body: { photo_path: path, weight_kg: Number(weight), ...here },
        }),
      );
    },
    onSuccess: () => {
      toast.info(copy.done);
      onClose();
    },
    onError: (e) => {
      if (e instanceof LocationError) form.fail({ location: e.message });
      else if (e instanceof PhotoError) form.fail({ photo: e.message });
      else if (e instanceof ApiError && Object.keys(e.fields).length) {
        const f = e.fields;
        form.fail({
          ...(f.photo_path || f.photo ? { photo: f.photo_path ?? f.photo } : {}),
          ...(f.weight_kg ? { weight_kg: f.weight_kg } : {}),
          ...(f.lat || f.lon ? { location: f.lat ?? f.lon } : {}),
        });
      }
      toast.error(e instanceof Error ? e.message : "Could not save this step.");
    },
    onSettled: () => {
      setStep("");
      for (const key of [JOBS_KEY, PAYOUTS_KEY, TRACK_KEY]) void qc.invalidateQueries({ queryKey: key });
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors: Errors = {};
    const photoError = validatePhotoFile(file);
    const weightError = validateWeightKg(weight);
    if (photoError) errors.photo = photoError;
    if (weightError) errors.weight_kg = weightError;
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    send.mutate();
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !send.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>{copy.title}</DialogTitle>
        <DialogDescription>
          {job.quantity_tonnes} t {job.residue_type} for {job.factory_name}. {copy.blurb}
        </DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} className="form-grid" aria-busy={send.isPending}>
          <fieldset disabled={send.isPending} className="bare-fieldset form-grid col-span-full">
            <Field label="Photo of the load" error={form.errors.photo} hint="JPEG, PNG or WebP, up to 5 MB">
              <input
                type="file"
                accept={PHOTO_TYPES.join(",")}
                capture="environment"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  form.clear("photo");
                }}
              />
            </Field>
            {preview && <img src={preview} alt="Selected photo" className="photo-preview" />}
            <Field
              label={copy.weightLabel}
              error={form.errors.weight_kg}
              hint={weightWarning(weight, job.est_weight_kg) ?? `The estimate is ${job.est_weight_kg} kg`}
            >
              <input
                inputMode="numeric"
                maxLength={LIMITS.weightText.max}
                value={weight}
                onChange={(e) => {
                  setWeight(e.target.value);
                  form.clear("weight_kg");
                }}
                onBlur={() => form.set("weight_kg", weight ? validateWeightKg(weight) : undefined)}
              />
            </Field>
            <div className="col-span-full">
              <p className="auth-note flex items-center gap-2">
                <MapPin size={14} />
                Your location is recorded with this step. Your phone will ask you to allow it.
              </p>
              {form.errors.location && <p className="field-error">{form.errors.location}</p>}
              {accuracy && <p className="field-hint">{accuracy}</p>}
              {step && (
                <p className="auth-note" role="status">
                  {step}
                </p>
              )}
            </div>
            <div className="col-span-full flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={send.isPending}>
                <Camera />
                {copy.button}
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}
