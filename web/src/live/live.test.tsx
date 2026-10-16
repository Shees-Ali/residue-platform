import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { usePoll } from "@/api/hooks";
import { api } from "@/api/client";
import { AuthProvider } from "@/auth/AuthProvider";
import { auth } from "@/lib/firebase";
import { LiveChip } from "@/components/live/NotificationBell";
import { ToastProvider } from "@/components/ui/toast";
import { me } from "@/test/renderApp";
import { LiveProvider } from "./LiveProvider";
import { useLiveStatus } from "./status";

// A hand-driven Firestore: the test decides what the inbox listener is told, and when.
const fs = vi.hoisted(() => ({
  subs: [] as {
    path: string;
    args: unknown[];
    next: (snap: unknown) => void;
    error: (e: unknown) => void;
    unsub: ReturnType<typeof vi.fn>;
  }[],
}));
vi.mock("firebase/firestore", () => ({
  collection: (_db: unknown, ...parts: string[]) => ({ path: parts.join("/") }),
  orderBy: (field: string, dir: string) => ({ orderBy: [field, dir] }),
  limit: (n: number) => ({ limit: n }),
  query: (c: { path: string }, ...rest: unknown[]) => ({ path: c.path, rest }),
  onSnapshot: (q: { path: string; rest: unknown[] }, _o: unknown, next: never, error: never) => {
    const unsub = vi.fn();
    fs.subs.push({ path: q.path, args: q.rest, next, error, unsub });
    return unsub;
  },
}));

type Doc = { id: string; title?: string; body?: string; level?: string; refresh?: string[] };
const snapshot = (docs: Doc[], opts: { fromCache?: boolean; added?: Doc[] } = {}) => ({
  metadata: { fromCache: opts.fromCache ?? false },
  docs: docs.map((d) => ({ id: d.id, data: () => d })),
  docChanges: () => (opts.added ?? []).map((d) => ({ type: "added", doc: { id: d.id, data: () => d } })),
});
const doc = (id: string, over: Partial<Doc> = {}): Doc => ({
  id, title: "Payment secured", body: "Green Mill funded the payment.", level: "info", refresh: ["jobs", "ledger"], ...over,
});

function Probe() {
  const status = useLiveStatus();
  return (
    <>
      <output aria-label="status">{status}</output>
      <output aria-label="poll">{usePoll(4000)}</output>
      <LiveChip />
    </>
  );
}

function setup(live = true) {
  const qc = new QueryClient();
  const invalidate = vi.spyOn(qc, "invalidateQueries");
  render(
    <ToastProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AuthProvider initial={{ status: "ready", user: me("transporter", { live_updates: live }) }}>
            <LiveProvider>
              <Probe />
            </LiveProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ToastProvider>,
  );
  return { invalidate };
}

const status = () => screen.getByLabelText("status").textContent;
const poll = () => screen.getByLabelText("poll").textContent;
const roots = (spy: { mock: { calls: unknown[][] } }) =>
  spy.mock.calls.map((c) => (c[0] as { queryKey?: string[] } | undefined)?.queryKey?.[0]);

beforeEach(() => {
  fs.subs.length = 0;
});

test("with no live updates from the API, nothing is listened to and screens poll as before", () => {
  setup(false);
  expect(fs.subs).toHaveLength(0);
  expect(status()).toBe("off");
  expect(poll()).toBe("4000");
});

test("it listens to the signed-in person's own inbox, newest first, twenty at a time", () => {
  setup();
  expect(fs.subs).toHaveLength(1);
  expect(fs.subs[0].path).toBe("users/u-transporter/inbox");
  expect(fs.subs[0].args).toEqual([{ orderBy: ["created_at", "desc"] }, { limit: 20 }]);
  expect(status()).toBe("connecting");
});

test("the first snapshot only catches up: no toast, everything refetched, polling slows down", () => {
  const { invalidate } = setup();
  act(() => fs.subs[0].next(snapshot([doc("old")], { added: [doc("old")] })));
  expect(status()).toBe("live");
  expect(screen.queryByText(/Payment secured/)).not.toBeInTheDocument();
  expect(invalidate).toHaveBeenCalledWith(); // refetch it all once
  expect(poll()).toBe("60000");
});

test("a new notification toasts and refetches the screens it names", () => {
  const { invalidate } = setup();
  act(() => fs.subs[0].next(snapshot([])));
  invalidate.mockClear();
  act(() => fs.subs[0].next(snapshot([doc("n1")], { added: [doc("n1")] })));
  expect(screen.getByText("Payment secured: Green Mill funded the payment.")).toBeInTheDocument();
  expect(roots(invalidate)).toEqual(["jobs", "ledger", "notifications"]);
});

test("a warning is shown as an alert, and the same notification never toasts twice", () => {
  setup();
  act(() => fs.subs[0].next(snapshot([])));
  const w = doc("w1", { title: "Farmer disputed a payment", body: "See the queue.", level: "warning", refresh: ["escalations"] });
  act(() => fs.subs[0].next(snapshot([w], { added: [w] })));
  expect(screen.getByRole("alert")).toHaveTextContent("Farmer disputed a payment: See the queue.");
  act(() => fs.subs[0].next(snapshot([w], { added: [w] })));
  expect(screen.getAllByText(/Farmer disputed a payment/)).toHaveLength(1);
});

test("an account notification re-reads who the person is", () => {
  (auth as unknown as { currentUser: unknown }).currentUser = { uid: "u-transporter", email: "t@x.pk", displayName: null };
  setup();
  act(() => fs.subs[0].next(snapshot([])));
  vi.mocked(api.GET).mockClear();
  const approved = doc("a1", { title: "Account approved", body: "You can start now.", refresh: ["me"] });
  act(() => fs.subs[0].next(snapshot([approved], { added: [approved] })));
  expect(vi.mocked(api.GET).mock.calls.some((c) => c[0] === "/api/me")).toBe(true);
  (auth as unknown as { currentUser: unknown }).currentUser = null;
});

test("going offline pauses it, shows the chip and polls every 30 seconds; coming back resumes", () => {
  setup();
  act(() => fs.subs[0].next(snapshot([])));
  expect(screen.queryByText(/Live updates paused/)).not.toBeInTheDocument();
  act(() => fs.subs[0].next(snapshot([], { fromCache: true })));
  expect(status()).toBe("paused");
  expect(screen.getByText(/Live updates paused · refreshing every 30 s/)).toBeInTheDocument();
  expect(poll()).toBe("30000");
  act(() => fs.subs[0].next(snapshot([])));
  expect(status()).toBe("live");
  expect(screen.queryByText(/Live updates paused/)).not.toBeInTheDocument();
});

test("a failed listener pauses, is started again after 15 seconds, and never leaks the old one", () => {
  vi.useFakeTimers();
  try {
    setup();
    act(() => fs.subs[0].error(new Error("permission denied")));
    expect(status()).toBe("paused");
    act(() => void vi.advanceTimersByTime(15_000));
    expect(fs.subs).toHaveLength(2);
    act(() => fs.subs[1].next(snapshot([])));
    expect(status()).toBe("live");
  } finally {
    vi.useRealTimers();
  }
});

test("leaving the page stops listening", () => {
  const view = (() => {
    const qc = new QueryClient();
    return render(
      <ToastProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <AuthProvider initial={{ status: "ready", user: me("factory", { live_updates: true }) }}>
              <LiveProvider>
                <Probe />
              </LiveProvider>
            </AuthProvider>
          </MemoryRouter>
        </QueryClientProvider>
      </ToastProvider>,
    );
  })();
  view.unmount();
  expect(fs.subs[0].unsub).toHaveBeenCalled();
});
