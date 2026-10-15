import { RecaptchaVerifier, linkWithPhoneNumber, type ConfirmationResult } from "firebase/auth";
import { auth } from "@/lib/firebase";

// One reCAPTCHA, created once and reused for every "send code". Drawing a second one into the same
// element is what makes Firebase say "reCAPTCHA has already been rendered in this element".
let verifier: RecaptchaVerifier | null = null;
let boundTo: HTMLElement | null = null;
let sending: Promise<ConfirmationResult> | null = null;

/** The one verifier for this element. Made on first use, then the same instance every time; made
 * again only if the element itself was replaced (the page was left and opened again). */
function verifierFor(containerId: string): RecaptchaVerifier {
  const el = document.getElementById(containerId);
  if (!el) throw new Error("The reCAPTCHA area is missing from the page. Reload and try again.");
  if (verifier && boundTo === el && el.isConnected) return verifier;
  disposeRecaptcha();
  el.innerHTML = "";
  verifier = new RecaptchaVerifier(auth, el, { size: "invisible" });
  boundTo = el;
  return verifier;
}

/** Throw the reCAPTCHA away (when the panel that owns it goes away). */
export function disposeRecaptcha(): void {
  try {
    verifier?.clear();
  } catch {
    /* it may already be gone */
  }
  if (boundTo) boundTo.innerHTML = "";
  verifier = null;
  boundTo = null;
  sending = null;
}

/** After a failed send the same verifier needs a fresh challenge: reset its widget, keep the instance. */
async function resetChallenge(): Promise<void> {
  try {
    const widgetId = await verifier?.render();
    (window as unknown as { grecaptcha?: { reset: (id?: number) => void } }).grecaptcha?.reset(widgetId);
  } catch {
    /* nothing to reset */
  }
}

/** Text a code to `phone` (E.164, e.g. +923001234567). Needs an element with id `containerId`
 * for the invisible reCAPTCHA. A second click while a send is running joins that send. The number
 * is linked to the signed-in account when the code is confirmed. */
export function sendPhoneCode(phone: string, containerId: string): Promise<ConfirmationResult> {
  if (!auth.currentUser) return Promise.reject(new Error("Sign in first"));
  if (sending) return sending;
  let v: RecaptchaVerifier;
  try {
    v = verifierFor(containerId);
  } catch (e) {
    return Promise.reject(e);
  }
  sending = linkWithPhoneNumber(auth.currentUser, phone, v)
    .catch(async (e) => {
      await resetChallenge();
      throw e;
    })
    .finally(() => {
      sending = null;
    });
  return sending;
}

/** Confirm the code, then refresh the ID token so the API sees the verified phone claim. */
export async function confirmPhoneCode(result: ConfirmationResult, code: string): Promise<void> {
  await result.confirm(code);
  await auth.currentUser?.getIdToken(true);
}
