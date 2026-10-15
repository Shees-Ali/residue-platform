import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Leaf } from "lucide-react";
import { ApiError } from "@/api/query";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PhoneInput } from "@/components/ui/phone-input";
import { useToast } from "@/components/ui/toast";
import { useAuth, type RegisterBody } from "@/auth/AuthProvider";
import { RedirectIfSettled } from "@/auth/guards";
import { PhoneVerifier } from "@/auth/PhoneVerifier";
import { PHONE_HELP, phoneProblem, type CountryCode } from "@/lib/phone";
import { useAction } from "@/auth/useAction";
import { SIGNUP_ROLES, type Role } from "@/lib/auth";
import { DISTRICTS, RESIDUES } from "@/lib/places";
import { useFormErrors } from "@/lib/useFormErrors";
import {
  LIMITS,
  pkrToPaisa,
  summarize,
  validateConfirm,
  validateEmail,
  validateNewPassword,
  validateProfile,
  validateText,
  type Errors,
} from "@/lib/validation";

type SignupRole = Exclude<Role, "admin">;

/** Farmers confirm their phone by SMS only when this is on (it matches the API's REQUIRE_VERIFIED_PHONE).
 * Off: the farmer's phone is an optional, unverified field. */
const REQUIRE_SMS = import.meta.env.VITE_REQUIRE_VERIFIED_PHONE === "true";

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
              maxLength={LIMITS.email.max}
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
              maxLength={LIMITS.password.max}
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
              maxLength={LIMITS.password.max}
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
  const [phoneTyped, setPhoneTyped] = useState<{ text: string; country: CountryCode } | null>(null);
  const [district, setDistrict] = useState<string>(DISTRICTS[0]);
  const [village, setVillage] = useState("");
  const [factoryName, setFactoryName] = useState("");
  const [price, setPrice] = useState("");
  const [residues, setResidues] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const form = useFormErrors();
  const toast = useToast();

  const [verified, setVerified] = useState(false); // farmer: the SMS code was confirmed

  function body(): RegisterBody {
    const base: RegisterBody = { role, display_name: name.trim() };
    if (role === "transporter") {
      return { ...base, phone, district, village: village.trim() };
    }
    if (role === "factory") {
      return {
        ...base,
        district,
        village: village.trim(),
        factory: { name: factoryName.trim(), price_per_tonne: pkrToPaisa(price) ?? 0, residues },
      };
    }
    return phone ? { ...base, phone } : base; // a farmer: the optional phone, only when given
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    // The farmer phone is verified by SMS, not typed into the body, so it needs the code step.
    const errors = validateProfile({ role, name, phone, district, village, factoryName, price, residues });
    if (role === "farmer" && REQUIRE_SMS && !verified) errors.phone ??= "Verify your phone number to continue";
    // optional, but if something was typed it has to be a real mobile number
    if (role === "farmer" && !REQUIRE_SMS && phoneTyped?.text && !phone) {
      errors.phone = phoneProblem(phoneTyped.text, phoneTyped.country) ?? PHONE_HELP;
    }
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
                min={1}
                max={1_000_000}
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
          <PhoneInput
            label="Phone"
            value={phone}
            error={err.phone}
            onChange={(e164) => {
              setPhone(e164);
              form.clear("phone");
            }}
          />
        )}

        {role === "farmer" && !REQUIRE_SMS && (
          <PhoneInput
            label="Phone (optional)"
            value={phone}
            error={err.phone}
            hint="Optional. Add it to see requests made earlier by phone."
            onChange={(e164, s) => {
              setPhone(e164);
              setPhoneTyped({ text: s.text, country: s.country });
              form.clear("phone");
            }}
          />
        )}

        {role === "farmer" && REQUIRE_SMS && (
          <PhoneVerifier
            error={err.phone}
            onChange={() => form.clear("phone")}
            onVerified={(verifiedPhone) => {
              setPhone(verifiedPhone);
              setVerified(true);
              form.clear("phone");
            }}
          />
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
