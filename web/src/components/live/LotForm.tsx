import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/api/client";
import { LOTS_KEY, useDistricts, useResidueTypes, useVillages } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PhoneInput } from "@/components/ui/phone-input";
import { useToast } from "@/components/ui/toast";
import { useFormErrors } from "@/lib/useFormErrors";
import {
  MAX_DAYS_AHEAD,
  PICKUP_PARTS,
  addDays,
  summarize,
  todayPkt,
  validateLot,
  validatePickupDate,
  validateQuantity,
  validateText,
  type Errors,
} from "@/lib/validation";

type Mode = "farmer" | "admin";

interface Props {
  mode: Mode;
  onDone: () => void;
  onCancel: () => void;
}

const newKey = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
const PART_LABEL = { morning: "Morning (6 to 12)", afternoon: "Afternoon (12 to 5)", evening: "Evening (5 to 8)" };

/** Report residue. The farmer reports their own; the admin enters one for a farmer by phone.
 * Both send the same fields the voice agent collects, with the same rules as the API. */
export function LotForm({ mode, onDone, onCancel }: Props) {
  const admin = mode === "admin";
  const today = todayPkt();
  const residues = useResidueTypes();
  const districts = useDistricts();
  const [farmerPhone, setFarmerPhone] = useState("");
  const [farmerName, setFarmerName] = useState("");
  const [residueType, setResidueType] = useState("");
  const [quantity, setQuantity] = useState("");
  const [pickupDate, setPickupDate] = useState(addDays(today, 1));
  const [pickupPart, setPickupPart] = useState<string>("morning");
  const [district, setDistrict] = useState("");
  const [village, setVillage] = useState("");
  // One key per opening of the form: pressing the button twice, or retrying, makes one lot.
  const [key] = useState(newKey);
  const chosenResidue = residueType || residues[0]?.code || "";
  const chosenDistrict = district || districts[0] || "";
  const suggestions = useVillages(chosenDistrict);
  const form = useFormErrors();
  const toast = useToast();
  const qc = useQueryClient();

  const send = useMutation({
    meta: { silent: true }, // this form shows its own errors, under the fields
    mutationFn: async (): Promise<{ factory: string | null }> => {
      const common = {
        residue_type: chosenResidue,
        quantity_tonnes: Number(quantity),
        pickup_date: pickupDate,
        pickup_part: pickupPart,
        village: village.trim(),
        district: chosenDistrict,
      };
      if (admin) {
        await unwrap(
          api.POST("/api/lots", {
            body: {
              ...common,
              farmer_phone: farmerPhone,
              farmer_name: farmerName.trim() || undefined,
            },
          }),
        );
        return { factory: null };
      }
      const lot = await unwrap(
        api.POST("/api/lots/mine", { body: common, params: { header: { "idempotency-key": key } } }),
      );
      return { factory: lot.factory_name ?? null };
    },
    onSuccess: ({ factory }) => {
      void qc.invalidateQueries({ queryKey: LOTS_KEY });
      toast.info(
        admin
          ? "Lot saved. It is now ranked for factories."
          : factory
            ? `Request saved. Matched to ${factory}.`
            : "Request saved. No factory takes this residue yet; an admin will follow up.",
      );
      onDone();
    },
    onError: (err) => {
      if (err instanceof ApiError && Object.keys(err.fields).length) form.fail(err.fields);
      toast.error(err instanceof Error ? err.message : "Could not save the request.");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors: Errors = validateLot(
      { residueType: chosenResidue, quantity, pickupDate, pickupPart, district: chosenDistrict, village, farmerPhone, farmerName },
      { admin, today },
    );
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    send.mutate();
  }

  const err = form.errors;
  return (
    <form noValidate ref={form.ref} onSubmit={submit} className="form-grid" aria-busy={send.isPending}>
      <fieldset disabled={send.isPending} className="bare-fieldset form-grid col-span-full">
        {admin && (
          <>
            <PhoneInput
              label="Farmer phone"
              value={farmerPhone}
              error={err.farmer_phone}
              onChange={(e164) => {
                setFarmerPhone(e164);
                form.clear("farmer_phone");
              }}
            />
            <Field label="Farmer name (only used for a new farmer)" error={err.farmer_name}>
              <input
                value={farmerName}
                maxLength={80}
                onChange={(e) => {
                  setFarmerName(e.target.value);
                  form.clear("farmer_name");
                }}
              />
            </Field>
          </>
        )}
        <Field label="Residue type" error={err.residue_type}>
          <select
            value={chosenResidue}
            onChange={(e) => {
              setResidueType(e.target.value);
              form.clear("residue_type");
            }}
          >
            {residues.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </Field>
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
            onBlur={() => form.set("quantity_tonnes", quantity ? validateQuantity(quantity) : undefined)}
          />
        </Field>
        <Field label="Pickup date" error={err.pickup_date} hint={`Within ${MAX_DAYS_AHEAD} days`}>
          <input
            type="date"
            min={today}
            max={addDays(today, MAX_DAYS_AHEAD)}
            value={pickupDate}
            onChange={(e) => {
              setPickupDate(e.target.value);
              form.clear("pickup_date");
            }}
            onBlur={() => form.set("pickup_date", validatePickupDate(pickupDate, today))}
          />
        </Field>
        <Field label="Pickup time" error={err.pickup_part}>
          <select
            value={pickupPart}
            onChange={(e) => {
              setPickupPart(e.target.value);
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
            value={chosenDistrict}
            onChange={(e) => {
              setDistrict(e.target.value);
              form.clear("district");
            }}
          >
            {districts.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </Field>
        <Field
          label="Village or area"
          error={err.village}
          hint="Pick a suggestion or type your own. Unknown places use the district centre."
        >
          <input
            list="village-suggestions"
            value={village}
            maxLength={80}
            onChange={(e) => {
              setVillage(e.target.value);
              form.clear("village");
            }}
            onBlur={() => form.set("village", validateText(village, "Village or area", 2, 80))}
          />
        </Field>
        <datalist id="village-suggestions">
          {suggestions.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        <div className="col-span-full flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" loading={send.isPending}>
            <Plus />
            {admin ? "Save lot" : "Report residue"}
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
