// Mirrors the API rules in memory/validation-rules.md. The API is the real guard; this gives
// instant, specific feedback. Keep messages identical to the API's. Field keys match the API's.

export type Errors = Record<string, string>;

export const PHONE_HELP = "Phone must include the country code, like +923001234567";
export const PRICE_HELP = "Price must be between PKR 1 and PKR 1,000,000 per tonne";
export const EMAIL_HELP = "Enter a valid email address, like name@example.com";
export const PASSWORD_HELP = "Use at least 8 characters with a letter and a number";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Clean a typed phone into E.164 (+923001234567), or null when it cannot be one. */
export function normalizePhone(raw: string): string | null {
  let v = raw.trim().replace(/[\s\-().]/g, "");
  if (v.startsWith("00")) v = "+" + v.slice(2);
  else if (/^03\d{9}$/.test(v)) v = "+92" + v.slice(1); // a local Pakistani mobile
  return /^\+[1-9]\d{7,14}$/.test(v) ? v : null;
}

export function validatePhone(raw: string): string | undefined {
  return normalizePhone(raw) ? undefined : PHONE_HELP;
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
  if (v.role === "transporter" || v.role === "farmer") add("phone", validatePhone(v.phone));
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
