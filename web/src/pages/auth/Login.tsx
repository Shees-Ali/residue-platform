import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Leaf } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/auth/AuthProvider";
import { RedirectIfSettled } from "@/auth/guards";
import { useAction } from "@/auth/useAction";
import { useFormErrors } from "@/lib/useFormErrors";
import { LIMITS, summarize, validateEmail, validateLoginPassword, type Errors } from "@/lib/validation";

export default function Login() {
  const { signInWithGoogle, signInWithEmail, state } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, run, cancel } = useAction();
  const [method, setMethod] = useState<"google" | "email">("email");
  // Working = the sign-in call OR the account lookup that follows it. The spinner covers both.
  const working = busy || state.status === "loading";
  const form = useFormErrors();
  const toast = useToast();

  function submit(e: FormEvent) {
    e.preventDefault();
    const errors: Errors = {};
    const emailError = validateEmail(email);
    const passwordError = validateLoginPassword(password);
    if (emailError) errors.email = emailError;
    if (passwordError) errors.password = passwordError;
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    setMethod("email");
    void run(() => signInWithEmail(email.trim(), password));
  }

  return (
    <div className="auth-page">
      <RedirectIfSettled stay={["signedOut", "loading", "error"]} />
      <div className="auth-card">
        <div className="auth-brand">
          <Leaf size={22} /> Residue Platform
        </div>
        <h1>Sign in</h1>
        <p className="lead">Welcome back. Use the account you signed up with.</p>
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
            <Field label="Password" error={form.errors.password}>
              <input
                type="password"
                maxLength={LIMITS.password.max}
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  form.clear("password");
                }}
              />
            </Field>
            <Button type="submit" loading={working && method === "email"}>
              Sign in
            </Button>
            </fieldset>
          </form>
          <p className="auth-note">
            New here? <Link to="/signup" className="underline">Create an account</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
