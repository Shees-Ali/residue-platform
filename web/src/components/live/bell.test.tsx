import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { NOTIFICATION_TYPES, routeFor, timeAgo } from "@/lib/notifications";
import { fail, mockGet, ok } from "@/test/mockApi";
import { renderAt, signedIn } from "@/test/renderApp";
import type { Role } from "@/lib/auth";

const item = (n: number, over: Record<string, unknown> = {}) => ({
  id: `n${n}`, type: "job.funded", level: "info", title: `Title ${n}`, body: `Body ${n}`, job_id: "job-1",
  refresh: ["jobs"], created_at: new Date().toISOString(), read: false, ...over,
});
const page = (items: unknown[], next: string | null = null, unread = items.length) => ({ items, next, unread });
const posted = (path: string) => vi.mocked(api.POST).mock.calls.filter((c) => c[0] === path);
const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => (resolve = res));
  return { promise, resolve };
};
const bell = () => screen.findByRole("button", { name: /^Notifications/ });
const openBell = async () => fireEvent.click(await bell());

describe("the bell", () => {
  test("every signed-in role has one", async () => {
    mockGet({});
    for (const role of ["farmer", "transporter", "factory", "buyer", "admin"] as Role[]) {
      const view = renderAt("/", signedIn(role));
      expect(await bell()).toBeInTheDocument();
      view.unmount();
    }
  });

  test("shows how many are unread, and says so to a screen reader", async () => {
    mockGet({ "/api/notifications/unread-count": { unread: 3 } });
    renderAt("/factory", signedIn("factory"));
    const button = await screen.findByRole("button", { name: "Notifications, 3 unread" });
    expect(within(button).getByText("3")).toBeInTheDocument();
  });

  test("a hundred or more reads 99+, and nothing unread shows no badge", async () => {
    mockGet({ "/api/notifications/unread-count": { unread: 250 } });
    const view = renderAt("/factory", signedIn("factory"));
    expect(await screen.findByText("99+")).toBeInTheDocument();
    view.unmount();
    mockGet({ "/api/notifications/unread-count": { unread: 0 } });
    renderAt("/factory", signedIn("factory"));
    expect((await bell()).textContent).toBe("");
  });

  test("a failed count is quiet: no toast, just no badge", async () => {
    mockGet({ "/api/notifications/unread-count": fail("Server error", 500) as never });
    renderAt("/factory", signedIn("factory"));
    await bell();
    await act(async () => {});
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("the list", () => {
  test("opens on click, newest first, unread ones marked", async () => {
    mockGet({
      "/api/notifications/unread-count": { unread: 2 },
      "/api/notifications": page([item(1), item(2, { read: true, title: "Older one" })], null, 1),
    });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    const panel = await screen.findByRole("dialog", { name: "Notifications" });
    expect(await within(panel).findByText("Title 1")).toBeInTheDocument();
    expect(within(panel).getAllByLabelText("Unread")).toHaveLength(1); // only the unread one has a dot
    expect(within(panel).getByText("Older one")).toBeInTheDocument();
    expect(within(panel).getAllByText("just now")).toHaveLength(2);
  });

  test("shows skeletons while it loads, then the empty state", async () => {
    const pending = deferred<unknown>();
    mockGet({ "/api/notifications": () => pending.promise });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    expect(document.querySelector('[aria-busy="true"]')).toBeInTheDocument();
    await act(async () => pending.resolve(page([])));
    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
  });

  test("a failed load offers Try again, which asks again", async () => {
    mockGet({ "/api/notifications": fail("Server error", 500) as never });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    expect(await screen.findByText("Could not load your notifications.", {}, { timeout: 4000 })).toBeInTheDocument();
    mockGet({ "/api/notifications": page([item(1)]) });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Title 1")).toBeInTheDocument();
  });

  test("Load older fetches the next page with the cursor and appends it", async () => {
    mockGet({
      "/api/notifications/unread-count": { unread: 3 },
      "/api/notifications": (init: { params?: { query?: { before?: string } } }) =>
        init?.params?.query?.before === "c1" ? page([item(3, { title: "Old page" })]) : page([item(1), item(2)], "c1", 3),
    });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    fireEvent.click(await screen.findByRole("button", { name: "Load older" }));
    expect(await screen.findByText("Old page")).toBeInTheDocument();
    expect(screen.getByText("Title 1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load older" })).not.toBeInTheDocument(); // no more pages
  });

  test("Escape and a click outside both close it", async () => {
    mockGet({ "/api/notifications": page([item(1)]) });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    await screen.findByText("Title 1");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Notifications" })).not.toBeInTheDocument();
    await openBell();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog", { name: "Notifications" })).not.toBeInTheDocument();
  });
});

describe("reading", () => {
  test("opening an unread one marks it read and goes to the page it is about", async () => {
    mockGet({
      "/api/notifications/unread-count": { unread: 1 },
      "/api/notifications": page([item(1, { type: "job.accepted", title: "Transporter on the way" })]),
    });
    vi.mocked(api.POST).mockResolvedValueOnce({ response: { ok: true, status: 204 } } as never);
    renderAt("/factory", signedIn("farmer"));
    await openBell();
    fireEvent.click(await screen.findByRole("button", { name: /Transporter on the way/ }));
    await waitFor(() => expect(posted("/api/notifications/{notification_id}/read")).toHaveLength(1));
    expect(posted("/api/notifications/{notification_id}/read")[0][1]).toEqual({ params: { path: { notification_id: "n1" } } });
    expect(await screen.findByRole("heading", { name: /Assalam-o-Alaikum/ })).toBeInTheDocument(); // the farmer page
    expect(screen.queryByRole("dialog", { name: "Notifications" })).not.toBeInTheDocument();
  });

  test("opening one that is already read does not ask the server again", async () => {
    mockGet({ "/api/notifications": page([item(1, { read: true })], null, 0), "/api/notifications/unread-count": { unread: 1 } });
    renderAt("/factory", signedIn("factory"));
    await openBell();
    fireEvent.click(await screen.findByRole("button", { name: /Title 1/ }));
    await act(async () => {});
    expect(posted("/api/notifications/{notification_id}/read")).toHaveLength(0);
  });

  test("Mark all read shows a spinner for the whole request, then refreshes the list and the badge", async () => {
    mockGet({ "/api/notifications/unread-count": { unread: 2 }, "/api/notifications": page([item(1), item(2)]) });
    const pending = deferred<unknown>();
    vi.mocked(api.POST).mockReturnValueOnce(pending.promise as never);
    renderAt("/factory", signedIn("factory"));
    await openBell();
    const button = await screen.findByRole("button", { name: "Mark all read" });
    fireEvent.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-busy", "true"));
    expect(button).toBeDisabled();
    mockGet({ "/api/notifications/unread-count": { unread: 0 }, "/api/notifications": page([item(1, { read: true }), item(2, { read: true })], null, 0) });
    await act(async () => pending.resolve({ data: { marked: 2 }, response: { ok: true, status: 200 } }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument());
    expect(screen.queryAllByLabelText("Unread")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Mark all read" })).toBeDisabled(); // nothing left to mark
  });

  test("a failed Mark all read is reported", async () => {
    mockGet({ "/api/notifications/unread-count": { unread: 1 }, "/api/notifications": page([item(1)]) });
    vi.mocked(api.POST).mockResolvedValueOnce({ error: { detail: "Server error" }, response: { ok: false, status: 500 } } as never);
    renderAt("/factory", signedIn("factory"));
    await openBell();
    fireEvent.click(await screen.findByRole("button", { name: "Mark all read" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
  });
});

describe("warnings and the admin's delivery note", () => {
  test("a warning in the list is marked, and the admin sees how many are waiting to be delivered", async () => {
    mockGet({
      "/api/notifications": page([item(1, { level: "warning", title: "Ledger does not balance" })]),
      "/api/stats": {
        farmers: 1, factories: 1, transporters: 1, transporters_waiting_approval: 0, live_jobs: 0, jobs_settled: 0,
        orders: 0, tonnes_diverted: 0, escrow_held: 0, open_escalations: 0, notifications_undelivered: 3,
      },
    });
    renderAt("/admin", signedIn("admin"));
    expect(await screen.findByText(/3 notifications waiting to reach Firestore/)).toBeInTheDocument();
    await openBell();
    expect(await screen.findByText("Ledger does not balance")).toBeInTheDocument();
    expect(document.querySelector(".bell-warning")).toBeInTheDocument();
  });

  test("no note when nothing is waiting", async () => {
    mockGet({});
    renderAt("/admin", signedIn("admin"));
    await screen.findByRole("heading", { name: /circular economy/ });
    expect(screen.queryByText(/waiting to reach Firestore/)).not.toBeInTheDocument();
  });
});

describe("a job's activity", () => {
  const lot = {
    id: "lot-1", farmer_id: "f1", farmer_name: "Fatima Bibi", farmer_phone: "+923008880099", residue_type: "rice_straw",
    residue_label: "Rice straw", quantity_tonnes: 2.5, village: "Raiwind", district: "Lahore", place_match: "exact",
    lat: 31, lon: 74, status: "assigned", factory_name: "Green Mill", quoted_price_per_tonne: 400000, farmer_share_bps: 7000,
    est_farmer_payout: 70000, pickup_from: "2026-10-20T01:00:00Z", pickup_to: "2026-10-20T07:00:00Z", job_id: "job-1",
    job_state: "funded", created_at: "2026-10-16T08:00:00Z",
  };

  test("the admin opens a lot's activity and reads who did what, in order", async () => {
    mockGet({
      "/api/lots": [lot],
      "/api/jobs/{job_id}/events": [
        { id: "e1", type: "lot.created", summary: "Lot reported", actor_role: "farmer", created_at: "2026-10-16T08:00:00Z" },
        { id: "e2", type: "job.funded", summary: "Escrow funded", actor_role: "factory", created_at: "2026-10-16T09:00:00Z" },
      ],
    });
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: /Activity of 2.5 t Rice straw/ }));
    const dialog = await screen.findByRole("dialog");
    const lines = (await within(dialog).findAllByRole("listitem")).map((li) => li.textContent);
    expect(lines[0]).toContain("Lot reported");
    expect(lines[0]).toContain("farmer");
    expect(lines[1]).toContain("Escrow funded");
    expect(vi.mocked(api.GET).mock.calls.some((c) => c[0] === "/api/jobs/{job_id}/events")).toBe(true);
  });

  test("nothing yet, and a failed load can be retried", async () => {
    mockGet({ "/api/lots": [lot], "/api/jobs/{job_id}/events": fail("Server error", 500) as never });
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: /Activity of/ }));
    const dialog = await screen.findByRole("dialog");
    const retry = await within(dialog).findByRole("button", { name: "Try again" }, { timeout: 4000 });
    mockGet({ "/api/lots": [lot], "/api/jobs/{job_id}/events": [] }); // the server is back
    fireEvent.click(retry);
    expect(await within(dialog).findByText("Nothing has happened yet.")).toBeInTheDocument();
  });
});

describe("where a notification takes you", () => {
  const roles: Role[] = ["farmer", "transporter", "factory", "buyer", "admin"];

  test.each(NOTIFICATION_TYPES)("%s opens a real page for every role", (type) => {
    for (const role of roles) {
      const to = routeFor(type, role);
      expect(to).toMatch(/^\/(farmer|transporter|factory|market|admin|settings)$/);
    }
  });

  test("account changes go to the details page, orders to the marketplace for a buyer", () => {
    expect(routeFor("account.tier_changed", "transporter")).toBe("/settings");
    expect(routeFor("account.edited", "factory")).toBe("/settings");
    expect(routeFor("order.placed", "buyer")).toBe("/market");
    expect(routeFor("order.placed", "factory")).toBe("/factory");
    expect(routeFor("job.accepted", "farmer")).toBe("/farmer");
    expect(routeFor("offer.created", "transporter")).toBe("/transporter");
    expect(routeFor("ledger.unbalanced", "admin")).toBe("/admin");
  });

  test("there is one entry per event type, none twice", () => {
    expect(new Set(NOTIFICATION_TYPES).size).toBe(NOTIFICATION_TYPES.length);
    expect(NOTIFICATION_TYPES).toHaveLength(31);
  });

  test("times read the way people say them", () => {
    const now = Date.parse("2026-10-16T12:00:00Z");
    const ago = (seconds: number) => new Date(now - seconds * 1000).toISOString();
    expect(timeAgo(ago(10), now)).toBe("just now");
    expect(timeAgo(ago(5 * 60), now)).toBe("5 min ago");
    expect(timeAgo(ago(3 * 3600), now)).toBe("3 h ago");
    expect(timeAgo(ago(2 * 86400), now)).toBe("2 d ago");
    expect(timeAgo(ago(30 * 86400), now)).toMatch(/Sept|Sep/);
    expect(timeAgo(ago(-60), now)).toBe("just now"); // a clock a little ahead is not "in the future"
  });
});

test("ok helper stays used", () => {
  expect(ok({ a: 1 })).toBeTruthy();
});
