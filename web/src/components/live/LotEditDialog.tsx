import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { JOBS_KEY, LOTS_KEY } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { DISTRICTS } from "@/lib/places";
import { useFormErrors } from "@/lib/useFormErrors";
import {
  LIMITS,
  MAX_DAYS_AHEAD,
  PICKUP_PARTS,
  addDays,
  summarize,
  todayPkt,
  validatePickupDate,
  validateQuantity,
  validateText,
  type Errors,
} from "@/lib/validation";
import { PART_LABEL } from "./LotForm";
import type { Lot } from "./lots";

type Edit = components["schemas"]["LotEditIn"];

/** The pickup day and part of day of a lot, in Pakistan time (the time the API stores them in). */
export function pickupOf(iso: string | null | undefined): { day: string; part: (typeof PICKUP_PARTS)[number] } {
  if (!iso) return { day: "", part: "morning" };
  const d = new Date(iso);
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Karachi" }).format(d);
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", hour: "2-digit", hour12: false }).format(d),
  );
  return { day, part: hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening" };
}

/** True while the lot can still be changed: no job yet, or the job has not been funded. */
export const canEditLot = (lot: Lot) => !lot.job_id || lot.job_state === "created";

/** Admin: change a lot until escrow is funded. The factory is ranked again for the new details. */
export function LotEditDialog({ lot, onClose }: { lot: Lot; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const form = useFormErrors();
  const start = pickupOf(lot.pickup_from);
  const initial = {
    quantity: String(lot.quantity_tonnes),
    day: start.day,
    part: start.part as string,
    district: lot.district ?? DISTRICTS[0],
    village: lot.village ?? "",
  };
  const [quantity, setQuantity] = useState(initial.quantity);
  const [day, setDay] = useState(initial.day);
  const [part, setPart] = useState(initial.part);
  const [district, setDistrict] = useState(initial.district);
  const [village, setVillage] = useState(initial.village);
  const today = todayPkt();

  function changes(): Edit {
    const body: Edit = {};
    if (quantity !== initial.quantity) body.quantity_tonnes = Number(quantity);
    if (day !== initial.day) body.pickup_date = day;
    if (part !== initial.part) body.pickup_part = part;
    if (district !== initial.district) body.district = district;
    if (village.trim() !== initial.village) body.village = village.trim();
    return body;
  }
  const dirty = Object.keys(changes()).length > 0;

  const save = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      unwrap(api.PATCH("/api/lots/{lot_id}", { params: { path: { lot_id: lot.id } }, body: changes() })),
    onSuccess: (out) => {
      toast.info(
        out.factory_name
          ? `Saved. This lot now goes to ${out.factory_name}.${out.override_dropped ? " The manual factory choice was replaced by the new ranking." : ""}`
          : "Saved. No factory buys this residue yet, so the lot is waiting.",
      );
      void qc.invalidateQueries({ queryKey: LOTS_KEY });
      void qc.invalidateQueries({ queryKey: JOBS_KEY });
      void qc.invalidateQueries({ queryKey: ["ranking", lot.id] });
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not change the lot.");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors: Errors = {};
    const put = (k: string, m: string | undefined) => {
      if (m) errors[k] = m;
    };
    if (quantity !== initial.quantity) put("quantity_tonnes", validateQuantity(quantity));
    if (day !== initial.day) put("pickup_date", validatePickupDate(day, today));
    if (village.trim() !== initial.village) put("village", validateText(village, "Village or area", 2, 80));
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    save.mutate();
  }

  const err = form.errors;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Edit lot</DialogTitle>
        <DialogDescription>
          {lot.residue_label ?? lot.residue_type} for {lot.farmer_name ?? "a farmer"}. You can change it until a
          factory funds it.
        </DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} aria-busy={save.isPending}>
          <fieldset className="bare-fieldset form-grid" disabled={save.isPending}>
            <Field label="Quantity (tonnes)" error={err.quantity_tonnes} hint="More than 0, up to 100">
              <input
                type="number"
                inputMode="decimal"
                step="any"
                min={0}
                max={100}
                value={quantity}
                onChange={(e) => {
                  setQuantity(e.target.value);
                  form.clear("quantity_tonnes");
                }}
              />
            </Field>
            <Field label="Pickup date" error={err.pickup_date} hint={`Within ${MAX_DAYS_AHEAD} days`}>
              <input
                type="date"
                min={today}
                max={addDays(today, MAX_DAYS_AHEAD)}
                value={day}
                onChange={(e) => {
                  setDay(e.target.value);
                  form.clear("pickup_date");
                }}
              />
            </Field>
            <Field label="Pickup time" error={err.pickup_part}>
              <select
                value={part}
                onChange={(e) => {
                  setPart(e.target.value);
                  form.clear("pickup_part");
                }}
              >
                {PICKUP_PARTS.map((p) => (
                  <option key={p} value={p}>
                    {PART_LABEL[p]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="District" error={err.district}>
              <select
                value={district}
                onChange={(e) => {
                  setDistrict(e.target.value);
                  form.clear("district");
                }}
              >
                {DISTRICTS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field label="Village or area" error={err.village} hint="Unknown places use the district centre.">
              <input
                value={village}
                maxLength={LIMITS.place.max}
                onChange={(e) => {
                  setVillage(e.target.value);
                  form.clear("village");
                }}
              />
            </Field>
            <div className="col-span-full flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={save.isPending} disabled={!dirty}>
                Save changes
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}
