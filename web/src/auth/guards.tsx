import { Navigate, Outlet, useLocation } from "react-router-dom";
import { canAccess, homeFor, type Role } from "@/lib/auth";
import { PageLoader } from "@/components/ui/spinner";
import { useAuth, type AuthState } from "./AuthProvider";

/** The page a person belongs on for their account state, or null if they may stay where they are. */
export function destinationFor(state: AuthState): string | null {
  switch (state.status) {
    case "signedOut":
      return "/login";
    case "needsRegistration":
      return "/signup";
    case "pending":
    case "suspended":
      return "/pending";
    case "ready":
      return null;
    default:
      return null; // loading and error render their own screen
  }
}

/** Auth pages (login, signup, pending): stay if the account state belongs here, else move on. */
export function RedirectIfSettled({ stay }: { stay: AuthState["status"][] }) {
  const { state, user } = useAuth();
  if (stay.includes(state.status)) return null;
  if (state.status === "ready" && user) return <Navigate to={homeFor(user.role as Role)} replace />;
  const to = destinationFor(state);
  return to ? <Navigate to={to} replace /> : null;
}

export function FullPageNotice({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card text-center" role="status">
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  );
}

/** Wraps the signed-in app: waits for the account, then sends people to login, signup or pending. */
export function RequireAuth() {
  const { state, refresh } = useAuth();
  const location = useLocation();
  if (state.status === "loading") return <PageLoader fullScreen label="Loading your workspace…" />;
  if (state.status === "error") {
    return (
      <FullPageNotice title="We could not reach the server">
        <p className="text-muted-foreground my-3">{state.message}</p>
        <button className="underline" onClick={() => void refresh()}>
          Try again
        </button>
      </FullPageNotice>
    );
  }
  const to = destinationFor(state);
  if (to) return <Navigate to={to} replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

/** A page only some roles may open. Everyone else is sent to their own home. */
export function RequireRole({ path, children }: { path: string; children: React.ReactNode }) {
  const { user } = useAuth();
  const role = user?.role as Role | undefined;
  if (!role) return null;
  if (!canAccess(path, role)) return <Navigate to={homeFor(role)} replace />;
  return <>{children}</>;
}

/** `/`: go to the signed-in person's own page. */
export function HomeRedirect() {
  const { user } = useAuth();
  return user ? <Navigate to={homeFor(user.role as Role)} replace /> : null;
}
