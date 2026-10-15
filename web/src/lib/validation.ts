// Mirrors the API rules in memory/validation-rules.md. The API is the real guard; this gives
// instant, specific feedback. Keep messages identical to the API's. Field keys match the API's.

import { PHONE_HELP, phoneProblem, toE164, type CountryCode } from "./phone";

export { PHONE_HELP };
export type Errors = Record<string, string>;

/** Length limits for every typed field, in one place. The API enforces the same ones
 * (memory/validation-rules.md, "Length limits"). `max` is also set as `maxLength` on the input. */
export const LIMITS = {
  email: { min: 5, max: 254 },
  password: { min: 8, max: 128 },
  name: { min: 2, max: 80 },
  place: { min: 2, max: 80 },
  factoryName: { min: 2, max: 120 },
  phoneText: { max: 22 },
  moneyText: { max: 12 },
  stockText: { max: 7 },
  weightText: { max: 6 },
  search: { max: 80 },
  reason: { min: 3, max: 500 },
  note: { min: 3, max: 1000 },
  productName: { min: 2, max: 120 },
  unit: { min: 2, max: 40 },
  description: { max: 500 },
} as const;

export const PRICE_HELP = "Price must be between PKR 1 and PKR 1,000,000 per tonne";
export const EMAIL_HELP = "Enter a valid email address, like name@example.com";
export const PASSWORD_HELP = "Use at least 8 characters with a letter and a number";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** A valid mobile number as E.164 (+923001234567), or null. `country` is how to read a number that
 * has no country code (the country picked in the phone input). */
export function normalizePhone(raw: string, country?: CountryCode): string | null {
  return toE164(raw, country);
}

/** The reason a phone number is not usable, naming its country; undefined when it is fine. */
export function validatePhone(raw: string, country?: CountryCode): string | undefined {
  return toE164(raw, country) ? undefined : (phoneProblem(raw, country) ?? PHONE_HELP);
}

export function validateEmail(raw: string): string | undefined {
  const v = raw.trim();
  if (!v) return "Enter your email address";
  return v.length > 254 || !EMAIL.test(v) ? EMAIL_HELP : undefined;
}

export const validateLoginPassword = (v: string) => (v ? undefined : "Enter your password");

export function validateNewPassword(v: string): string | undefined {
  const ok = v.length >= 8 && v.length <= 128 && /[A-Za-z]/.test(v) && /\d/.test(v);
  return ok ? undefined : PASSWORD_HELP;
}

export const validateConfirm = (password: string, confirm: string) =>
  password === confirm ? undefined : "Passwords do not match";

export function validateText(raw: string, label: string, min: number, max: number): string | undefined {
  const v = raw.trim();
  if (!v) return `${label} is required`;
  if (v.length < min) return `${label} must be at least ${min} characters`;
  if (v.length > max) return `${label} must be at most ${max} characters`;
  return undefined;
}

/** Whole paisa for a typed PKR amount, or null if it is not a number. */
export function pkrToPaisa(raw: string): number | null {
  const n = Number(raw.trim());
  return raw.trim() !== "" && Number.isFinite(n) ? Math.round(n * 100) : null;
}

export function validatePrice(raw: string): string | undefined {
  if (!raw.trim()) return "Price per tonne is required";
  const paisa = pkrToPaisa(raw);
  if (paisa === null) return "Price per tonne must be a number";
  return paisa >= 100 && paisa <= 100_000_000 ? undefined : PRICE_HELP;
}

export interface ProfileValues {
  role: "farmer" | "buyer" | "transporter" | "factory";
  name: string;
  phone: string;
  district: string;
  village: string;
  factoryName: string;
  price: string;
  residues: string[];
}

/** Errors for the role step of signup, keyed by the API field names. Empty means valid. */
export function validateProfile(v: ProfileValues): Errors {
  const e: Errors = {};
  const add = (key: string, msg: string | undefined) => {
    if (msg) e[key] = msg;
  };
  add("display_name", validateText(v.name, "Name", 2, 80));
  if (v.role === "transporter") add("phone", validatePhone(v.phone)); // a farmer's phone is optional
  if (v.role === "transporter" || v.role === "factory") {
    add("district", v.district ? undefined : "District is required");
    add("village", validateText(v.village, "Village or area", 2, 80));
  }
  if (v.role === "factory") {
    add("factory.name", validateText(v.factoryName, "Factory name", 2, 120));
    add("factory.price_per_tonne", validatePrice(v.price));
    add("factory.residues", v.residues.length ? undefined : "Choose at least one residue you buy");
  }
  return e;
}

/** One line for a toast, the same wording the API uses for its `detail`. */
export function summarize(errors: Errors): string {
  const messages = Object.values(errors);
  return messages.length === 1 ? messages[0] : `Fix ${messages.length} fields: ${messages.join("; ")}`;
}

// --- Report residue (farmer form and admin entry). Same rules as the API; see validation-rules.md.

export const QUANTITY_HELP = "Quantity must be more than 0 and at most 100 tonnes";
export const PICKUP_PARTS = ["morning", "afternoon", "evening"] as const;
export const MAX_DAYS_AHEAD = 60;

/** Today as YYYY-MM-DD in Pakistan time, which is what the API compares pickup dates to. */
export function todayPkt(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Karachi" }).format(now);
}

export function addDays(day: string, days: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function validateQuantity(raw: string): string | undefined {
  const v = raw.trim();
  if (!v) return "Quantity is required";
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0 || n > 100) return QUANTITY_HELP;
  return /^\d+(\.\d{1,2})?$/.test(v) ? undefined : "Quantity can have at most 2 decimals";
}

export function validatePickupDate(raw: string, today: string = todayPkt()): string | undefined {
  if (!raw) return "Pickup date is required";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw) || Number.isNaN(Date.parse(raw))) {
    return "Pickup date must be a real date, like 2026-10-20";
  }
  if (raw < today) return "Pickup date cannot be in the past";
  if (raw > addDays(today, MAX_DAYS_AHEAD)) return `Pickup date must be within ${MAX_DAYS_AHEAD} days`;
  return undefined;
}

export interface LotValues {
  residueType: string;
  quantity: string;
  pickupDate: string;
  pickupPart: string;
  district: string;
  village: string;
  farmerPhone?: string; // admin entry only
  farmerName?: string; // admin entry only
}

/** Errors for the report-residue form, keyed by the API field names. Empty means valid. */
export function validateLot(v: LotValues, opts: { admin?: boolean; today?: string } = {}): Errors {
  const e: Errors = {};
  const add = (key: string, msg: string | undefined) => {
    if (msg) e[key] = msg;
  };
  if (opts.admin) {
    add("farmer_phone", validatePhone(v.farmerPhone ?? ""));
    if ((v.farmerName ?? "").trim().length > 80) e.farmer_name = "Name must be at most 80 characters";
  }
  add("residue_type", v.residueType ? undefined : "Choose a residue type");
  add("quantity_tonnes", validateQuantity(v.quantity));
  add("pickup_date", validatePickupDate(v.pickupDate, opts.today));
  add(
    "pickup_part",
    (PICKUP_PARTS as readonly string[]).includes(v.pickupPart)
      ? undefined
      : "Pickup time must be morning, afternoon or evening",
  );
  add("district", v.district ? undefined : "District is required");
  add("village", validateText(v.village, "Village or area", 2, 80));
  return e;
}

// --- Delivery: photo, weight and place (pickup, delivery, weighbridge) -------------------------

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;
export const PHOTO_HELP = "Add a photo (JPEG, PNG or WebP, up to 5 MB)";
export const WEIGHT_HELP = "Weight must be a whole number of kilograms between 1 and 100,000";
export const LOCATION_HELP = "Allow location access to record this step";

export function validatePhotoFile(file: { type: string; size: number } | null | undefined): string | undefined {
  if (!file) return PHOTO_HELP;
  if (!(PHOTO_TYPES as readonly string[]).includes(file.type)) return PHOTO_HELP;
  if (file.size === 0) return "The photo file is empty";
  if (file.size > PHOTO_MAX_BYTES) return "Photo must be 5 MB or smaller";
  return undefined;
}

export function validateWeightKg(raw: string): string | undefined {
  const v = raw.trim();
  if (!v) return "Weight is required";
  return /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 100_000 ? undefined : WEIGHT_HELP;
}

/** A soft warning (never blocks) when a weight is far from the estimate. */
export function weightWarning(raw: string, estimateKg: number): string | undefined {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0 || estimateKg <= 0) return undefined;
  return Math.abs(n - estimateKg) / estimateKg > 0.5
    ? `That is far from the estimated ${estimateKg} kg. Check the weight.`
    : undefined;
}

/** A soft warning when the phone says it may be off by a long way. */
export function accuracyWarning(accuracyM: number | null | undefined): string | undefined {
  return accuracyM != null && accuracyM > 500
    ? `Your location is only accurate to ${Math.round(accuracyM)} m. Move outdoors and try again.`
    : undefined;
}
