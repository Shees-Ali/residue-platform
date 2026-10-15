import { RecaptchaVerifier, linkWithPhoneNumber, type ConfirmationResult } from "firebase/auth";
import { auth } from "@/lib/firebase";

/** Text a code to `phone` (E.164, e.g. +923001234567). Needs an element with id `containerId`
 * for the invisible reCAPTCHA. The number is linked to the signed-in account on confirm. */
export async function sendPhoneCode(phone: string, containerId: string): Promise<ConfirmationResult> {
  if (!auth.currentUser) throw new Error("Sign in first");
  const verifier = new RecaptchaVerifier(auth, containerId, { size: "invisible" });
  try {
    return await linkWithPhoneNumber(auth.currentUser, phone, verifier);
  } catch (e) {
    verifier.clear();
    throw e;
  }
}

/** Confirm the code, then refresh the ID token so the API sees the verified phone claim. */
export async function confirmPhoneCode(result: ConfirmationResult, code: string): Promise<void> {
  await result.confirm(code);
  await auth.currentUser?.getIdToken(true);
}
