import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "@/App";
import { QueryProvider } from "@/api/QueryProvider";
import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider, type AuthState, type Me } from "@/auth/AuthProvider";
import type { Role } from "@/lib/auth";

export function me(role: Role, extra: Partial<Me> = {}): Me {
  return {
    uid: `u-${role}`,
    email: `${role}@example.pk`,
    role,
    status: "active",
    display_name: "Test User",
    phone: null,
    ...(role === "farmer" ? { farmer_linked: true } : {}),
    ...extra,
  };
}

export const signedIn = (role: Role): AuthState => ({ status: "ready", user: me(role) });

/** Render the whole app at `path` with a fixed account state (no Firebase, no network). */
export function renderAt(path: string, state: AuthState) {
  return render(
    <ToastProvider>
      <QueryProvider>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider initial={state}>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </QueryProvider>
    </ToastProvider>,
  );
}

/** Render one component with the toast and server-state providers the app wraps everything in. */
export function renderWithProviders(ui: ReactElement) {
  return render(
    <ToastProvider>
      <QueryProvider>{ui}</QueryProvider>
    </ToastProvider>,
  );
}
