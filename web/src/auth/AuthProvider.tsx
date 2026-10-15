import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
} from "firebase/auth";
import { api } from "@/api/client";
import { apiErrorFrom } from "@/api/query";
import { errorMessage } from "@/api/errors";
import type { components } from "@/api/schema";
import { useToast } from "@/components/ui/toast";
import { auth, googleProvider } from "@/lib/firebase";

export type Me = components["schemas"]["MeOut"];
export type RegisterBody = components["schemas"]["RegisterIn"];

export type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "needsRegistration"; email: string | null; name: string | null }
  | { status: "pending"; user: Me }
  | { status: "suspended"; user: Me }
  | { status: "ready"; user: Me }
  | { status: "error"; message: string };

function stateForMe(me: Me): AuthState {
  if (me.status === "pending") return { status: "pending", user: me };
  if (me.status === "suspended") return { status: "suspended", user: me };
  return { status: "ready", user: me };
}

async function loadProfile(email: string | null, name: string | null): Promise<AuthState> {
  const { data, error, response } = await api.GET("/api/me");
  if (response.status === 404) return { status: "needsRegistration", email, name };
  if (!data) return { status: "error", message: errorMessage(error, "Could not load your account.") };
  return stateForMe(data);
}

interface AuthContextValue {
  state: AuthState;
  /** The signed-in, active person; null in every other state. */
  user: Me | null;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  /** First sign-in: choose a role. Throws an Error with a readable message if refused. */
  register: (body: RegisterBody) => Promise<void>;
  /** Re-read the account, e.g. after an admin approves it or a phone was verified. */
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** `initial` skips Firebase entirely (tests, previews): the state is fixed until signOut. */
export function AuthProvider({ children, initial }: { children: ReactNode; initial?: AuthState }) {
  const [state, setState] = useState<AuthState>(initial ?? { status: "loading" });
  const toast = useToast();

  const refresh = useCallback(async () => {
    const fb = auth.currentUser;
    if (!fb) return setState({ status: "signedOut" });
    try {
      const next = await loadProfile(fb.email, fb.displayName);
      // e.g. "Invalid token": say why, since a 401 also signs the person out.
      if (next.status === "error") toast.error(next.message);
      // Signed out (or switched) while we waited: the auth listener already set the right state.
      if (auth.currentUser?.uid !== fb.uid) return;
      setState(next);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Network error";
      toast.error(`Could not reach the server: ${message}`);
      if (auth.currentUser?.uid === fb.uid) setState({ status: "error", message });
    }
  }, [toast]);

  useEffect(() => {
    if (initial) return;
    return onAuthStateChanged(auth, (fb) => {
      if (!fb) return setState({ status: "signedOut" });
      setState({ status: "loading" });
      void refresh();
    });
  }, [initial, refresh]);

  /** Run a Firebase sign-in. Firebase only announces a change of person, so signing in again as the
   * person already signed in (a signup left half done, a lookup that failed) announces nothing and
   * the screen would stay where it was. In that case look the account up now: an unregistered
   * account then resumes at step 2, a registered one goes home. */
  const signedInBy = useCallback(
    async (call: () => Promise<unknown>) => {
      const before = auth.currentUser?.uid ?? null;
      await call();
      if (!initial && auth.currentUser && auth.currentUser.uid === before) {
        setState({ status: "loading" });
        await refresh();
      }
    },
    [initial, refresh],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      user: state.status === "ready" ? state.user : null,
      signInWithGoogle: () => signedInBy(() => signInWithPopup(auth, googleProvider)),
      signInWithEmail: (email, password) =>
        signedInBy(() => signInWithEmailAndPassword(auth, email, password)),
      signUpWithEmail: (email, password) =>
        signedInBy(() => createUserWithEmailAndPassword(auth, email, password)),
      register: async (body) => {
        const { data, error, response } = await api.POST("/api/me/register", { body });
        if (!data) throw apiErrorFrom(error, response.status);
        setState(stateForMe(data));
      },
      refresh,
      signOut: async () => {
        if (initial) return setState({ status: "signedOut" });
        await auth.signOut();
      },
    }),
    [state, refresh, initial, signedInBy],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** A readable message for a Firebase sign-in error code. */
export function firebaseMessage(e: unknown): string {
  const code = typeof e === "object" && e && "code" in e ? String((e as { code: unknown }).code) : "";
  const known: Record<string, string> = {
    "auth/invalid-credential": "Wrong email or password.",
    "auth/user-not-found": "Wrong email or password.",
    "auth/wrong-password": "Wrong email or password.",
    "auth/email-already-in-use": "That email already has an account. Sign in instead.",
    "auth/weak-password": "Use a password of at least 6 characters.",
    "auth/invalid-email": "That email address does not look right.",
    "auth/popup-closed-by-user": "Sign-in was cancelled.",
    "auth/cancelled-popup-request": "", // a second click replaced the first popup: nothing to say
    "auth/popup-blocked": "Your browser blocked the sign-in window. Allow pop-ups for this site.",
    "auth/network-request-failed": "Could not reach Google. Check your internet connection.",
    "auth/too-many-requests": "Too many attempts. Wait a moment and try again.",
    "auth/invalid-phone-number": "Enter the phone number like +923001234567.",
    "auth/invalid-verification-code": "That code is not right.",
    "auth/credential-already-in-use": "That phone number is already used by another account.",
    "auth/operation-not-allowed":
      "This sign-in method is not turned on for the project. In the Firebase console open Authentication, Sign-in method, and enable it (Phone for SMS codes). If Phone is on, check Authentication, Settings, SMS region policy allows Pakistan.",
    "auth/billing-not-enabled":
      "Real SMS messages need billing on the Firebase project. Add a test phone number in the console, or turn billing on.",
    "auth/quota-exceeded": "Too many SMS messages were sent today. Try a test phone number or wait.",
    "auth/captcha-check-failed": "The reCAPTCHA check failed. Reload the page and try again.",
    "auth/missing-phone-number": "Enter your phone number first.",
    "auth/unauthorized-domain":
      "This address is not allowed to sign in. In the Firebase console add it under Authentication, Settings, Authorized domains.",
    "auth/invalid-app-credential": "The reCAPTCHA check was rejected. Reload the page and try again.",
    "auth/code-expired": "That code has expired. Ask for a new one.",
  };
  return code in known ? known[code] : (e instanceof Error ? e.message : "Something went wrong. Try again.");
}
