import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { signInWithEmailAndPassword, signInWithPopup } from "firebase/auth";
import App from "@/App";
import { QueryProvider } from "@/api/QueryProvider";
import { api } from "@/api/client";
import { AuthProvider } from "@/auth/AuthProvider";
import { ToastProvider } from "@/components/ui/toast";
import { auth } from "@/lib/firebase";
import { me, renderAt } from "@/test/renderApp";

// A controllable Firebase: the test decides when sign-in finishes and when the auth listener fires.
const hooks = vi.hoisted(() => ({ notify: (_user: unknown) => {} }));
vi.mock("firebase/auth", async (orig) => ({
  ...(await orig<typeof import("firebase/auth")>()),
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: unknown) => void) => {
    hooks.notify = cb;
    cb(null);
    return () => {};
  }),
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
}));

const setUser = (u: unknown) => ((auth as unknown as { currentUser: unknown }).currentUser = u);
const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => (resolve = res));
  return { promise, resolve };
};

function renderLive() {
  return render(
    <ToastProvider>
      <QueryProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </QueryProvider>
    </ToastProvider>,
  );
}

afterEach(() => setUser(null));

const fillAndSubmit = () => {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.pk" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret123" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
};

test("the spinner keeps going through the account lookup that follows sign-in", async () => {
  const lookup = deferred<unknown>();
  vi.mocked(api.GET).mockReturnValueOnce(lookup.promise as never);
  vi.mocked(signInWithEmailAndPassword).mockImplementation((async () => {
    setUser({ uid: "u1", email: "a@b.pk", displayName: null });
    hooks.notify(auth.currentUser); // Firebase tells the app first, then resolves the call
  }) as never);

  renderLive();
  fillAndSubmit();
  await waitFor(() => expect(api.GET).toHaveBeenCalled()); // /api/me is now in flight
  await act(async () => {}); // sign-in has resolved; only the lookup is outstanding

  const button = screen.getByRole("button", { name: "Sign in" });
  expect(button).toHaveAttribute("aria-busy", "true");
  expect(button).toBeDisabled();
  expect(screen.getByLabelText("Email")).toBeDisabled();

  await act(async () => lookup.resolve({ data: me("buyer"), response: { status: 200 } }));
  expect(await screen.findByRole("heading", { name: "Good for you. Better for the planet." })).toBeInTheDocument();
});

test("an unregistered account moves on to the role step once the lookup answers", async () => {
  vi.mocked(api.GET).mockResolvedValueOnce({ error: { detail: {} }, response: { status: 404 } } as never);
  vi.mocked(signInWithEmailAndPassword).mockImplementation((async () => {
    setUser({ uid: "u2", email: "new@b.pk", displayName: "New Person" });
    hooks.notify(auth.currentUser);
  }) as never);
  renderLive();
  fillAndSubmit();
  expect(await screen.findByRole("heading", { name: "How will you use it?" })).toBeInTheDocument();
  expect(screen.getByLabelText("Your name")).toHaveValue("New Person");
});

test("the Google button spins until the popup settles, with a Cancel the person controls", async () => {
  vi.useFakeTimers();
  try {
    vi.mocked(signInWithPopup).mockReturnValue(new Promise(() => {}) as never); // never reports
    renderLive();
    fireEvent.click(screen.getByRole("button", { name: /Continue with Google/ }));
    act(() => {
      window.dispatchEvent(new Event("focus"));
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("button", { name: /Continue with Google/ })).toHaveAttribute("aria-busy", "true");
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(screen.getByRole("button", { name: /Continue with Google/ })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Cancel/ })).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

test("a failed account lookup is toasted with the reason, not swallowed", async () => {
  vi.mocked(api.GET).mockResolvedValueOnce({
    error: { detail: "Invalid token: this computer's clock is behind." },
    response: { status: 401 },
  } as never);
  vi.mocked(signInWithEmailAndPassword).mockImplementation((async () => {
    setUser({ uid: "u3", email: "a@b.pk", displayName: null });
    hooks.notify(auth.currentUser);
  }) as never);
  renderLive();
  fillAndSubmit();
  expect(await screen.findByRole("alert")).toHaveTextContent("clock is behind");
});

test("signing in again as the same person looks the account up again and resumes step 2", async () => {
  // First the lookup fails (server hiccup), so the person is signed in to Firebase but has no account state.
  vi.mocked(api.GET).mockResolvedValueOnce({ error: { detail: "Server error" }, response: { status: 500 } } as never);
  renderLive();
  setUser({ uid: "u5", email: "half@b.pk", displayName: "Half Way" });
  await act(async () => hooks.notify(auth.currentUser));
  await waitFor(() => expect(api.GET).toHaveBeenCalledTimes(1));

  // They sign in again with the same account. Firebase announces nothing (same person), and the
  // account is not registered yet: they must land on step 2, not stay on the sign-in page.
  vi.mocked(api.GET).mockResolvedValueOnce({ error: { detail: {} }, response: { status: 404 } } as never);
  vi.mocked(signInWithEmailAndPassword).mockResolvedValue({} as never);
  fillAndSubmit();
  expect(await screen.findByRole("heading", { name: "How will you use it?" })).toBeInTheDocument();
  expect(api.GET).toHaveBeenCalledTimes(2);
});

test("a loading account state disables the login form, even before anything is clicked", () => {
  renderAt("/login", { status: "loading" });
  expect(screen.getByLabelText("Email")).toBeDisabled();
});

test("Check again on the pending page shows a spinner while it asks", async () => {
  const lookup = deferred<unknown>();
  setUser({ uid: "u4", email: "t@x.pk", displayName: null });
  vi.mocked(api.GET).mockReturnValueOnce(lookup.promise as never);
  renderAt("/pending", { status: "pending", user: me("transporter", { status: "pending" }) });
  fireEvent.click(screen.getByRole("button", { name: "Check again" }));
  expect(screen.getByRole("button", { name: "Check again" })).toHaveAttribute("aria-busy", "true");
  await act(async () => lookup.resolve({ data: me("transporter", { status: "pending" }), response: { status: 200 } }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Check again" })).not.toHaveAttribute("aria-busy"));
});
