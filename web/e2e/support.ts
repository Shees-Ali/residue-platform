import { expect, type APIRequestContext, type Browser, type BrowserContext, type Page } from "@playwright/test";

export const AUTH = "http://127.0.0.1:9099";
export const FIRESTORE = "http://127.0.0.1:8080";
export const API = "http://127.0.0.1:8010";
export const PROJECT = "demo-residue";
export const PASSWORD = "Passw0rd!x";
export const ADMIN_EMAIL = "admin@e2e.test"; // BOOTSTRAP_ADMIN_EMAILS in api/scripts/run_e2e_api.py

let serial = 0;
export const email = (prefix: string) => `${prefix}-${Date.now().toString(36)}${serial++}@e2e.test`;

export type Role = "farmer" | "factory" | "transporter" | "buyer";
export interface Person {
  email: string;
  uid: string;
  role: Role | "admin";
  token: string;
}

const IDENTITY = `${AUTH}/identitytoolkit.googleapis.com/v1`;

async function signIn(request: APIRequestContext, mail: string) {
  const r = await request.post(`${IDENTITY}/accounts:signInWithPassword?key=e2e`, {
    data: { email: mail, password: PASSWORD, returnSecureToken: true },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  const body = await r.json();
  return { uid: body.localId as string, token: body.idToken as string };
}

/** A Firebase account on the Auth emulator (or the existing one with that email). */
export async function ensureAccount(request: APIRequestContext, mail: string) {
  const made = await request.post(`${IDENTITY}/accounts:signUp?key=e2e`, {
    data: { email: mail, password: PASSWORD, returnSecureToken: true },
  });
  if (made.ok()) {
    const body = await made.json();
    return { uid: body.localId as string, token: body.idToken as string };
  }
  return signIn(request, mail);
}

/** Mark the email verified (the API makes only a verified listed email an admin). */
async function verifyEmail(request: APIRequestContext, uid: string) {
  const r = await request.post(`${IDENTITY}/projects/${PROJECT}/accounts:update`, {
    headers: { Authorization: "Bearer owner" },
    data: { localId: uid, emailVerified: true },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
}

export async function call(request: APIRequestContext, token: string, method: string, path: string, data?: unknown, headers: Record<string, string> = {}) {
  const r = await request.fetch(`${API}${path}`, {
    method,
    data,
    headers: { Authorization: `Bearer ${token}`, ...headers },
  });
  return { ok: r.ok(), status: r.status(), body: await r.json().catch(() => null), text: await r.text().catch(() => "") };
}

export async function must(request: APIRequestContext, token: string, method: string, path: string, data?: unknown, headers: Record<string, string> = {}) {
  const r = await call(request, token, method, path, data, headers);
  expect(r.ok, `${method} ${path} -> ${r.status} ${r.text}`).toBeTruthy();
  return r.body;
}

/** The admin: the one listed in BOOTSTRAP_ADMIN_EMAILS, with a verified email. */
export async function admin(request: APIRequestContext): Promise<Person> {
  const { uid } = await ensureAccount(request, ADMIN_EMAIL);
  await verifyEmail(request, uid);
  const { token } = await signIn(request, ADMIN_EMAIL);
  const me = await must(request, token, "GET", "/api/me"); // makes them admin
  expect(me.role).toBe("admin");
  return { email: ADMIN_EMAIL, uid, role: "admin", token };
}

const REGISTER: Record<Role, (residue: string) => Record<string, unknown>> = {
  farmer: () => ({ role: "farmer", display_name: "Fatima Bibi" }),
  buyer: () => ({ role: "buyer", display_name: "Bilal Ahmed" }),
  factory: (residue) => ({
    role: "factory", display_name: "Mill Owner", district: "Lahore", village: "Raiwind",
    // the dearest price allowed, so this factory outranks any other for its residue
    factory: { name: "E2E Mill", price_per_tonne: 100_000_000, residues: [residue] },
  }),
  transporter: () => ({
    role: "transporter", display_name: "Truck Driver", phone: "+923001234567", district: "Lahore", village: "Raiwind",
  }),
};

/** Sign up a person through the API (an account on the emulator, then their role), approved if the role needs it. */
export async function person(request: APIRequestContext, role: Role, boss: Person, residue = "rice_straw"): Promise<Person> {
  const mail = email(role);
  const { uid, token } = await ensureAccount(request, mail);
  await must(request, token, "POST", "/api/me/register", REGISTER[role](residue));
  if (role === "factory" || role === "transporter") {
    await must(request, boss.token, "POST", `/api/users/${uid}/approve`, { tier: 1 });
  }
  return { email: mail, uid, role, token: (await signIn(request, mail)).token };
}

/** Take a factory and a transporter out of the running, so later specs are offered to their own. */
export async function retire(request: APIRequestContext, boss: Person, ...people: Person[]) {
  for (const p of people) await call(request, boss.token, "POST", `/api/users/${p.uid}/suspend`);
}

/** A browser that is a person: its own context, geolocation granted, signed in through the real form. */
export async function browserFor(browser: Browser, who: Person): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:5183",
    geolocation: { latitude: 31.2476, longitude: 74.2143 }, // Raiwind
  });
  const origin = "http://127.0.0.1:5183";
  await context.grantPermissions(["geolocation"], { origin });
  await oneReadingInsteadOfAWatch(context);
  const page = await context.newPage();
  await signInThroughTheForm(page, who.email);
  return { context, page };
}

/** Chromium's emulated GPS cannot serve a fresh reading (the app asks for maximumAge 0 at pickup and
 * delivery) while a watchPosition is open: it times out. A real phone does both. So in the browser tests
 * the live tracker's watch is replaced by a single reading; pickup and delivery still read the position. */
function oneReadingInsteadOfAWatch(context: BrowserContext) {
  return context.addInitScript(() => {
    navigator.geolocation.watchPosition = (ok, err, options) => {
      navigator.geolocation.getCurrentPosition(ok, err, options);
      return 1;
    };
    navigator.geolocation.clearWatch = () => {};
  });
}

export async function signInThroughTheForm(page: Page, mail: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(mail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 });
}

/** What the server says this person has unread (specs share one admin, so counts are measured, not assumed). */
export async function serverUnread(request: APIRequestContext, who: Person): Promise<number> {
  return (await must(request, who.token, "GET", "/api/notifications/unread-count")).unread;
}

export const bell = (page: Page) => page.getByRole("button", { name: /^Notifications/ });

/** The number on the bell, read from its accessible name ("Notifications, 3 unread"). */
export async function unread(page: Page): Promise<number> {
  const name = (await bell(page).getAttribute("aria-label")) ?? "";
  return Number(/(\d+) unread/.exec(name)?.[1] ?? 0);
}

export async function expectUnread(page: Page, n: number) {
  await expect(bell(page)).toHaveAttribute("aria-label", n === 0 ? "Notifications" : `Notifications, ${n} unread`, { timeout: 30_000 });
}

/** Open the bell and return the titles it lists, newest first. */
export async function titles(page: Page): Promise<string[]> {
  await bell(page).click();
  const panel = page.getByRole("dialog", { name: "Notifications" });
  await expect(panel).toBeVisible();
  await expect(panel.locator(".bell-title").first()).toBeVisible();
  const list = await panel.locator(".bell-title").allInnerTexts();
  await page.keyboard.press("Escape");
  return list.map((t) => t.trim());
}

export function tomorrow(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000 + 5 * 3600 * 1000); // a day ahead, in Pakistan time
  return d.toISOString().slice(0, 10);
}

export const JPEG = { name: "load.jpg", mimeType: "image/jpeg", buffer: Buffer.from("ffd8ffe000104a46494600010100000100010000ffd9", "hex") };

/** Report a lot as the farmer, through the API. Returns the job id. */
export async function reportLot(request: APIRequestContext, farmer: Person, residue = "rice_straw", tonnes = 2.5): Promise<string> {
  const lot = await must(request, farmer.token, "POST", "/api/lots/mine", {
    residue_type: residue, quantity_tonnes: tonnes, pickup_date: tomorrow(), pickup_part: "morning", village: "Raiwind", district: "Lahore",
  }, { "Idempotency-Key": `e2e-${Date.now()}-${serial++}` });
  return lot.job_id as string;
}

/** Drive a job over the API from funded to confirmed (heavy lifting for specs that test only the end). */
export async function driveToConfirmed(request: APIRequestContext, p: { factory: Person; transporter: Person; jobId: string; weightKg?: number }) {
  const { factory, transporter, jobId } = p;
  await must(request, factory.token, "POST", `/api/jobs/${jobId}/fund`);
  const offers = await must(request, transporter.token, "GET", "/api/offers");
  const offer = offers.find((o: { job_id: string }) => o.job_id === jobId);
  await must(request, transporter.token, "POST", `/api/offers/${offer.id}/accept`);
  for (const [kind, path, kg] of [["pickup", "pickup", 2450], ["delivery", "deliver", 2440]] as const) {
    const slot = await must(request, transporter.token, "POST", `/api/jobs/${jobId}/photos/upload-url`, { kind });
    const put = await request.put(`${API}${slot.upload_url}`, {
      headers: { Authorization: `Bearer ${transporter.token}`, "Content-Type": "image/jpeg" },
      data: JPEG.buffer,
    });
    expect(put.status()).toBe(204);
    await must(request, transporter.token, "POST", `/api/jobs/${jobId}/${path}`, { photo_path: slot.path, weight_kg: kg, lat: 31.2476, lon: 74.2143 });
  }
  await must(request, factory.token, "POST", `/api/jobs/${jobId}/confirm`, { accept: true, final_weight_kg: p.weightKg ?? 2480 });
}
