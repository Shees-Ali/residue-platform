import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { PROFILE_KEY } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PhoneInput } from "@/components/ui/phone-input";
import { useToast } from "@/components/ui/toast";
import { DISTRICTS, RESIDUES } from "@/lib/places";
import type { CountryCode } from "@/lib/phone";
import { useFormErrors } from "@/lib/useFormErrors";
import { LIMITS, pkrToPaisa, summarize, validateProfileEdit } from "@/lib/validation";

export type Profile = components["schemas"]["ProfileOut"];
type EditBody = components["schemas"]["ProfileEditIn"];

interface Props {
  profile: Profile;
  /** The admin editing this person (tier and max load are editable, the endpoint is by uid). */
  admin?: boolean;
  onSaved: (updated: Profile) => void;
  onCancel?: () => void;
}

const PLACE_ROLES = ["transporter", "factory"];
const paisaToPkr = (paisa: number) => String(paisa / 100);

/** Edit my details (or, for an admin, anyone's). Only the fields that changed are sent. */
export function ProfileForm({ profile, admin = false, onSaved, onCancel }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const form = useFormErrors();
  const hasPlace = PLACE_ROLES.includes(profile.role);

  const initial = {
    name: profile.display_name,
    phone: profile.phone ?? "",
    district: profile.district ?? "",
    village: profile.village ?? "",
    factoryName: profile.factory?.name ?? "",
    price: profile.factory ? paisaToPkr(profile.factory.price_per_tonne) : "",
    residues: profile.factory?.residues ?? [],
    tier: profile.transporter ? String(profile.transporter.tier) : "",
    maxTonnes: profile.transporter ? String(profile.transporter.max_tonnes) : "",
  };
  const [name, setName] = useState(initial.name);
  const [phone, setPhone] = useState(initial.phone);
  const [typed, setTyped] = useState<{ text: string; country: CountryCode } | null>(null);
  const [district, setDistrict] = useState(initial.district);
  const [village, setVillage] = useState(initial.village);
  const [factoryName, setFactoryName] = useState(initial.factoryName);
  const [price, setPrice] = useState(initial.price);
  const [residues, setResidues] = useState<string[]>(initial.residues);
  const [tier, setTier] = useState(initial.tier);
  const [maxTonnes, setMaxTonnes] = useState(initial.maxTonnes);
  const [phoneKey, setPhoneKey] = useState(0); // remounts the phone box on Reset

  const placeChanged = district !== initial.district || village.trim() !== initial.village;
  const sameResidues =
    residues.length === initial.residues.length && residues.every((r) => initial.residues.includes(r));

  /** Only what changed. The API changes nothing it is not sent. */
  function changes(): EditBody {
    const body: EditBody = {};
    if (name.trim() !== initial.name) body.display_name = name.trim();
    if (phone && phone !== initial.phone) body.phone = phone;
    if (hasPlace) {
      if (district !== initial.district) body.district = district;
      if (village.trim() !== initial.village) body.village = village.trim();
    }
    if (profile.role === "factory") {
      const f: NonNullable<EditBody["factory"]> = {};
      if (factoryName.trim() !== initial.factoryName) f.name = factoryName.trim();
      if (price !== initial.price) f.price_per_tonne = pkrToPaisa(price) ?? 0;
      if (!sameResidues) f.residues = residues;
      if (Object.keys(f).length) body.factory = f;
    }
    if (admin && profile.role === "transporter") {
      const t: NonNullable<EditBody["transporter"]> = {};
      if (tier !== initial.tier) t.tier = Number(tier);
      if (maxTonnes !== initial.maxTonnes && maxTonnes.trim() !== "") t.max_tonnes = Number(maxTonnes);
      if (Object.keys(t).length) body.transporter = t;
    }
    return body;
  }
  const body = changes();
  const dirty = Object.keys(body).length > 0 || Boolean(typed?.text && !phone);

  const save = useMutation({
    meta: { silent: true },
    mutationFn: () =>
      admin
        ? unwrap(
            api.PATCH("/api/users/{uid}/profile", {
              params: { path: { uid: profile.uid } },
              body: changes(),
            }),
          )
        : unwrap(api.PATCH("/api/me/profile", { body: changes() })),
    onSuccess: (updated) => {
      toast.info("Saved.");
      void qc.invalidateQueries({ queryKey: PROFILE_KEY });
      void qc.invalidateQueries({ queryKey: ["users"] });
      void qc.invalidateQueries({ queryKey: ["transporters"] });
      onSaved(updated);
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not save your changes.");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors = validateProfileEdit({
      role: profile.role,
      name,
      phone,
      typed,
      district,
      village,
      placeChanged,
      factoryName,
      price,
      residues,
      tier: admin && profile.transporter ? tier : undefined,
      maxTonnes: admin && profile.transporter ? maxTonnes : undefined,
    });
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    save.mutate();
  }

  function reset() {
    setName(initial.name);
    setPhone(initial.phone);
    setTyped(null);
    setPhoneKey((k) => k + 1);
    setDistrict(initial.district);
    setVillage(initial.village);
    setFactoryName(initial.factoryName);
    setPrice(initial.price);
    setResidues(initial.residues);
    setTier(initial.tier);
    setMaxTonnes(initial.maxTonnes);
    form.reset();
  }

  const err = form.errors;
  const phoneLabel = profile.role === "transporter" ? "Phone" : "Phone (optional)";
  return (
    <form noValidate ref={form.ref} onSubmit={submit} className="auth-stack" aria-busy={save.isPending}>
      <fieldset className="bare-fieldset auth-stack" disabled={save.isPending}>
        <p className="auth-note">
          {profile.email ?? "No email on file"} · {profile.role} · {profile.status}
        </p>

        <Field label="Your name" error={err.display_name}>
          <input
            value={name}
            maxLength={LIMITS.name.max}
            onChange={(e) => {
              setName(e.target.value);
              form.clear("display_name");
            }}
          />
        </Field>

        <PhoneInput
          key={phoneKey}
          label={phoneLabel}
          value={phone}
          error={err.phone}
          onChange={(e164, s) => {
            setPhone(e164);
            setTyped({ text: s.text, country: s.country });
            form.clear("phone");
          }}
        />

        {profile.role === "factory" && (
          <>
            <Field label="Factory name" error={err["factory.name"]}>
              <input
                value={factoryName}
                maxLength={LIMITS.factoryName.max}
                onChange={(e) => {
                  setFactoryName(e.target.value);
                  form.clear("factory.name");
                }}
              />
            </Field>
            <Field
              label="Price you pay per tonne (PKR)"
              error={err["factory.price_per_tonne"]}
              hint="Between PKR 1 and PKR 1,000,000. Jobs already assigned keep the price they were quoted."
            >
              <input
                inputMode="decimal"
                maxLength={LIMITS.moneyText.max}
                value={price}
                onChange={(e) => {
                  setPrice(e.target.value);
                  form.clear("factory.price_per_tonne");
                }}
              />
            </Field>
            <fieldset className="form-field">
              <legend className="text-xs font-medium">Residues you buy</legend>
              <div className="check-row">
                {RESIDUES.map((r) => (
                  <label key={r.code}>
                    <input
                      type="checkbox"
                      checked={residues.includes(r.code)}
                      onChange={(e) => {
                        setResidues(e.target.checked ? [...residues, r.code] : residues.filter((c) => c !== r.code));
                        form.clear("factory.residues");
                      }}
                    />
                    {r.label}
                  </label>
                ))}
              </div>
              {err["factory.residues"] && <p className="field-error">{err["factory.residues"]}</p>}
            </fieldset>
          </>
        )}

        {hasPlace && (
          <div className="form-grid">
            <Field label="District" error={err.district}>
              <select
                value={district}
                onChange={(e) => {
                  setDistrict(e.target.value);
                  form.clear("district");
                }}
              >
                {!district && <option value="">Not set</option>}
                {DISTRICTS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field
              label="Village or area"
              error={err.village}
              hint={profile.role === "factory" ? "Where the factory is. New lots are ranked from here." : "Your base. Offers go to the nearest transporter."}
            >
              <input
                value={village}
                maxLength={LIMITS.place.max}
                onChange={(e) => {
                  setVillage(e.target.value);
                  form.clear("village");
                }}
              />
            </Field>
          </div>
        )}

        {profile.role === "transporter" && profile.transporter && !admin && (
          <p className="auth-note">
            Tier {profile.transporter.tier}, max load {profile.transporter.max_tonnes} t.{" "}
            {profile.transporter.approved ? "" : "Not approved yet. "}An admin sets these.
          </p>
        )}

        {admin && profile.role === "transporter" && profile.transporter && (
          <div className="form-grid">
            <Field label="Tier" error={err["transporter.tier"]} hint="The largest job they are offered">
              <select
                value={tier}
                onChange={(e) => {
                  setTier(e.target.value);
                  form.clear("transporter.tier");
                }}
              >
                <option value="1">Tier 1 (3 t)</option>
                <option value="2">Tier 2 (7 t)</option>
                <option value="3">Tier 3 (15 t)</option>
              </select>
            </Field>
            <Field
              label="Max load (tonnes)"
              error={err["transporter.max_tonnes"]}
              hint="More than 0, up to 100. Changing the tier resets this to the tier's load unless you set it too."
            >
              <input
                inputMode="decimal"
                maxLength={6}
                value={maxTonnes}
                onChange={(e) => {
                  setMaxTonnes(e.target.value);
                  form.clear("transporter.max_tonnes");
                }}
              />
            </Field>
          </div>
        )}

        <div className="flex justify-end gap-2">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="button" variant="outline" disabled={!dirty} onClick={reset}>
            Reset
          </Button>
          <Button type="submit" loading={save.isPending} disabled={!dirty}>
            Save changes
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
