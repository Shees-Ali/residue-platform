import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { ConfirmationResult } from "firebase/auth";
import { Leaf } from "lucide-react";
import { ApiError } from "@/api/query";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { firebaseMessage, useAuth, type RegisterBody } from "@/auth/AuthProvider";
import { RedirectIfSettled } from "@/auth/guards";
import { confirmPhoneCode, sendPhoneCode } from "@/auth/phone";
import { useAction } from "@/auth/useAction";
import { SIGNUP_ROLES, type Role } from "@/lib/auth";
import { DISTRICTS, RESIDUES } from "@/lib/places";
import { useFormErrors } from "@/lib/useFormErrors";
import {
  normalizePhone,
  pkrToPaisa,
  summarize,
  validateConfirm,
  validateEmail,
  validateNewPassword,
  validatePhone,
  validateProfile,
  validateText,
  type Errors,
} from "@/lib/validation";

type SignupRole = Exclude<Role, "admin">;

export default function Signup() {
  const { state } = useAuth();
  return (
    <div className="auth-page">
      <RedirectIfSettled stay={["signedOut", "needsRegistration", "loading", "error"]} />
      {state.status === "needsRegistration" ? (
        <ProfileStep defaultName={state.name ?? ""} />
      ) : (
        <AccountStep />
      )}
    </div>
  );
}

/** Step 1: make a Firebase account (Google or email and password). */
function AccountStep() {
  const { signInWithGoogle, signUpWithEmail, state } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const { busy, run, cancel } = useAction();
  const [method, setMethod] = useState<"google" | "email">("email");
  // Working = the sign-in call OR the account lookup that follows it. The spinner covers both.
  const working = busy || state.status === "loading";
  const form = useFormErrors();
  const toast = useToast();

  function submit(e: FormEvent) {
    e.preventDefault();
    const found: Errors = {};
    const checks: [string, string | undefined][] = [
      ["email", validateEmail(email)],
      ["password", validateNewPassword(password)],
      ["confirm", validateConfirm(password, confirm)],
    ];
    for (const [key, message] of checks) if (message) found[key] = message;
    if (Object.keys(found).length) {
      form.fail(found);
      toast.error(summarize(found));
      return;
    }
    form.reset();
    setMethod("email");
    void run(() => signUpWithEmail(email.trim(), password));
  }

  return (
    <div className="auth-card">
      <div className="auth-brand">
        <Leaf size={22} /> Residue Platform
      </div>
      <h1>Create your account</h1>
      <p className="lead">Step 1 of 2. Next you choose how you will use the platform.</p>
      <div className="auth-stack">
        <Button
          type="button"
          variant="outline"
          loading={working && method === "google"}
          disabled={working}
          onClick={() => {
            setMethod("google");
            void run(signInWithGoogle);
          }}
        >
          Continue with Google
        </Button>
        {busy && method === "google" && (
          <button type="button" className="auth-note underline" onClick={cancel}>
            Waiting for Google. Closed the window? Cancel
          </button>
        )}
        <div className="auth-divider">or</div>
        <form className="auth-stack" noValidate ref={form.ref} onSubmit={submit} aria-busy={working}>
          <fieldset className="bare-fieldset auth-stack" disabled={working}>
          <Field label="Email" error={form.errors.email}>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                form.clear("email");
              }}
              onBlur={() => form.set("email", email ? validateEmail(email) : undefined)}
            />
          </Field>
          <Field label="Password" error={form.errors.password} hint="8 or more characters, with a letter and a number">
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                form.clear("password");
              }}
              onBlur={() => form.set("password", password ? validateNewPassword(password) : undefined)}
            />
          </Field>
          <Field label="Confirm password" error={form.errors.confirm}>
            <input
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => {
                setConfirm(e.target.value);
                form.clear("confirm");
              }}
            />
          </Field>
          <Button type="submit" loading={working && method === "email"}>
            Create account
          </Button>
          </fieldset>
        </form>
        <p className="auth-note">
          Already have an account? <Link to="/login" className="underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

/** Step 2: choose a role and give the details that role needs. */
function ProfileStep({ defaultName }: { defaultName: string }) {
  const { register, signOut } = useAuth();
  const [role, setRole] = useState<SignupRole>("farmer");
  const [name, setName] = useState(defaultName);
  const [phone, setPhone] = useState("");
  const [district, setDistrict] = useState<string>(DISTRICTS[0]);
  const [village, setVillage] = useState("");
  const [factoryName, setFactoryName] = useState("");
  const [price, setPrice] = useState("");
  const [residues, setResidues] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const form = useFormErrors();
  const toast = useToast();

  // farmer phone verification
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<ConfirmationResult | null>(null);
  const [verified, setVerified] = useState(false);

  async function sendCode() {
    const problem = validatePhone(phone);
    if (problem) {
      form.fail({ phone: problem });
      toast.error(problem);
      return;
    }
    setBusy(true);
    try {
      setSent(await sendPhoneCode(normalizePhone(phone)!, "recaptcha-container"));
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
      form.fail({ code: "Enter the 6-digit code from the SMS" });
      return;
    }
    setBusy(true);
    try {
      await confirmPhoneCode(sent, code.trim());
      setVerified(true);
      form.reset();
    } catch (e) {
      const message = firebaseMessage(e);
      form.fail({ code: message || "That code is not right." });
      if (message) toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  function body(): RegisterBody {
    const base: RegisterBody = { role, display_name: name.trim() };
    if (role === "transporter") {
      return { ...base, phone: normalizePhone(phone) ?? phone.trim(), district, village: village.trim() };
    }
    if (role === "factory") {
      return {
        ...base,
        district,
        village: village.trim(),
        factory: { name: factoryName.trim(), price_per_tonne: pkrToPaisa(price) ?? 0, residues },
      };
    }
    return base;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    // The farmer phone is verified by SMS, not typed into the body, so it needs the code step.
    const errors = validateProfile({ role, name, phone, district, village, factoryName, price, residues });
    if (role === "farmer" && !verified) errors.phone ??= "Verify your phone number to continue";
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    setBusy(true);
    try {
      await register(body());
    } catch (err) {
      if (err instanceof ApiError) {
        form.fail(err.fields); // marks the exact fields the API objected to
        toast.error(err.message);
      } else {
        toast.error(err instanceof Error ? err.message : "Could not create your account.");
      }
    } finally {
      setBusy(false);
    }
  }

  const needsPlace = role === "transporter" || role === "factory";
  const waitsForApproval = needsPlace;
  const err = form.errors;
  return (
    <div className="auth-card wide">
      <div className="auth-brand">
        <Leaf size={22} /> Residue Platform
      </div>
      <h1>How will you use it?</h1>
      <p className="lead">
        Step 2 of 2. {waitsForApproval ? "An admin approves transporters and factories before they start." : ""}
      </p>
      <form className="auth-stack" noValidate ref={form.ref} onSubmit={(e) => void submit(e)}>
        <div className="role-cards" role="radiogroup" aria-label="Your role">
          {SIGNUP_ROLES.map((r) => (
            <button
              type="button"
              role="radio"
              aria-checked={role === r.role}
              key={r.role}
              className="role-card"
              onClick={() => {
                setRole(r.role);
                form.reset();
              }}
            >
              <strong>{r.label}</strong>
              <span>{r.blurb}</span>
            </button>
          ))}
        </div>

        <Field label="Your name" error={err.display_name}>
          <input
            value={name}
            maxLength={80}
            onChange={(e) => {
              setName(e.target.value);
              form.clear("display_name");
            }}
            onBlur={() => form.set("display_name", validateText(name, "Name", 2, 80))}
          />
        </Field>

        {role === "factory" && (
          <>
            <Field label="Factory name" error={err["factory.name"]}>
              <input
                value={factoryName}
                maxLength={120}
                onChange={(e) => {
                  setFactoryName(e.target.value);
                  form.clear("factory.name");
                }}
                onBlur={() => form.set("factory.name", validateText(factoryName, "Factory name", 2, 120))}
              />
            </Field>
            <Field
              label="Price you pay per tonne (PKR)"
              error={err["factory.price_per_tonne"]}
              hint="Between PKR 1 and PKR 1,000,000"
            >
              <input
                type="number"
                inputMode="decimal"
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

        {needsPlace && (
          <div className="form-grid">
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
            <Field label="Village or area" error={err.village}>
              <input
                value={village}
                maxLength={80}
                onChange={(e) => {
                  setVillage(e.target.value);
                  form.clear("village");
                }}
                onBlur={() => form.set("village", validateText(village, "Village or area", 2, 80))}
              />
            </Field>
          </div>
        )}

        {role === "transporter" && (
          <Field label="Phone (like +923001234567)" error={err.phone}>
            <input
              type="tel"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                form.clear("phone");
              }}
              onBlur={() => form.set("phone", phone ? validatePhone(phone) : undefined)}
            />
          </Field>
        )}

        {role === "farmer" && (
          <div className="auth-stack">
            <Field label="Your phone number (like +923001234567)" error={err.phone}>
              <input
                type="tel"
                disabled={verified}
                value={phone}
                onChange={(e) => {
                  setPhone(e.target.value);
                  form.clear("phone");
                }}
              />
            </Field>
            <p className="auth-note">
              We text you a code. It proves the number is yours, so you see only your own lots and payments.
            </p>
            {verified ? (
              <p className="auth-note" role="status">Phone verified.</p>
            ) : sent ? (
              <div className="form-grid">
                <Field label="6-digit code" error={err.code}>
                  <input
                    inputMode="numeric"
                    maxLength={6}
                    value={code}
                    onChange={(e) => {
                      setCode(e.target.value.replace(/\D/g, ""));
                      form.clear("code");
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
        )}

        <Button type="submit" loading={busy}>
          {waitsForApproval ? "Submit for approval" : "Finish"}
        </Button>
        <button type="button" className="auth-note underline" onClick={() => void signOut()}>
          Use a different account
        </button>
      </form>
    </div>
  );
}
