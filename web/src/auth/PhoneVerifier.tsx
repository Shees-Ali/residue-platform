import { useEffect, useState } from "react";
import type { ConfirmationResult } from "firebase/auth";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PhoneInput } from "@/components/ui/phone-input";
import { useToast } from "@/components/ui/toast";
import { PHONE_HELP } from "@/lib/phone";
import { firebaseMessage } from "./AuthProvider";
import { confirmPhoneCode, disposeRecaptcha, sendPhoneCode } from "./phone";

interface Props {
  /** Called once the SMS code is confirmed, with the number in international form. */
  onVerified: (phone: string) => void | Promise<void>;
  /** An error from the surrounding form (for example "Verify your phone number to continue"). */
  error?: string;
  onChange?: () => void;
}

/** Pick a country, type a mobile number, get a code by SMS, confirm it. Firebase proves the number
 * is theirs. The reCAPTCHA is made once and reused for every "send code". */
export function PhoneVerifier({ onVerified, error, onChange }: Props) {
  const [phone, setPhone] = useState(""); // E.164 when the number is valid, "" otherwise
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<ConfirmationResult | null>(null);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ phone?: string; code?: string }>({});
  const toast = useToast();

  // leaving the page (or this panel) throws the reCAPTCHA away so a later visit starts clean
  useEffect(() => disposeRecaptcha, []);

  async function sendCode() {
    if (!phone) {
      setProblem({ phone: PHONE_HELP });
      toast.error("Enter a valid mobile number for the country you picked.");
      return;
    }
    setProblem({});
    setBusy(true);
    try {
      setSent(await sendPhoneCode(phone, "recaptcha-container"));
      toast.info("We sent a 6-digit code by SMS.");
    } catch (e) {
      const message = firebaseMessage(e);
      if (message) toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    if (!sent) return;
    if (!/^\d{6}$/.test(code.trim())) {
      setProblem({ code: "Enter the 6-digit code from the SMS" });
      return;
    }
    setProblem({});
    setBusy(true);
    try {
      await confirmPhoneCode(sent, code.trim());
      setVerified(true);
      await onVerified(phone);
    } catch (e) {
      const message = firebaseMessage(e);
      setProblem({ code: message || "That code is not right." });
      if (message) toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-stack">
      <PhoneInput
        label="Your mobile number"
        value={phone}
        disabled={verified || Boolean(sent)}
        error={problem.phone ?? error}
        onChange={(e164) => {
          setPhone(e164);
          setProblem({});
          onChange?.();
        }}
      />
      <p className="auth-note">
        We text you a code. It proves the number is yours, so you see only your own lots and payments.
      </p>
      {verified ? (
        <p className="auth-note" role="status">
          Phone verified.
        </p>
      ) : sent ? (
        <div className="form-grid">
          <Field label="6-digit code" error={problem.code}>
            <input
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => {
                setCode(e.target.value.replace(/\D/g, ""));
                setProblem({});
              }}
            />
          </Field>
          <Button type="button" loading={busy} onClick={() => void verify()}>
            Verify code
          </Button>
        </div>
      ) : (
        <Button type="button" variant="outline" loading={busy} onClick={() => void sendCode()}>
          Send code
        </Button>
      )}
      <div id="recaptcha-container" />
    </div>
  );
}
