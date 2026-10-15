import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { fail, mockGet, ok } from "@/test/mockApi";
import { me, renderAt, signedIn } from "@/test/renderApp";

const factoryProfile = (over: Record<string, unknown> = {}) => ({
  uid: "u-factory", email: "factory@example.pk", role: "factory", status: "active",
  display_name: "Owner One", phone: null, district: "Lahore", village: "Raiwind",
  factory: { name: "Green Mill", price_per_tonne: 400000, residues: ["rice_straw"] },
  transporter: null, ...over,
});
const transporterProfile = (over: Record<string, unknown> = {}) => ({
  uid: "u-transporter", email: "t@example.pk", role: "transporter", status: "active",
  display_name: "Truck Co", phone: "+923009990001", district: "Lahore", village: "Raiwind",
  factory: null, transporter: { tier: 1, max_tonnes: 3, approved: true }, ...over,
});

const patched = (path: string) => vi.mocked(api.PATCH).mock.calls.filter((c) => c[0] === path);
const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const save = () => screen.getByRole("button", { name: "Save changes" });
const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => (resolve = res));
  return { promise, resolve };
};

describe("Settings: a factory edits its own details", () => {
  beforeEach(() => mockGet({ "/api/me/profile": factoryProfile() }));

  test("shows what is saved and keeps Save off until something changes", async () => {
    renderAt("/settings", signedIn("factory"));
    expect(await screen.findByLabelText("Factory name")).toHaveValue("Green Mill");
    expect(screen.getByLabelText(/Price you pay/)).toHaveValue("4000");
    expect(screen.getByLabelText("Rice straw")).toBeChecked();
    expect(screen.getByLabelText("Village or area")).toHaveValue("Raiwind");
    expect(save()).toBeDisabled();
    type("Factory name", "Green Mill 2");
    expect(save()).toBeEnabled();
  });

  test("sends only the fields that changed, then says it saved", async () => {
    vi.mocked(api.PATCH).mockResolvedValueOnce(
      ok(factoryProfile({ factory: { name: "Green Mill", price_per_tonne: 500000, residues: ["rice_straw"] } })),
    );
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    type(/Price you pay/, "5000");
    fireEvent.click(save());
    await waitFor(() => expect(patched("/api/me/profile")).toHaveLength(1));
    expect(patched("/api/me/profile")[0][1]).toEqual({ body: { factory: { price_per_tonne: 500000 } } });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  test("a wrong price is explained next to the field and nothing is sent", async () => {
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    type(/Price you pay/, "0");
    fireEvent.click(save());
    expect(await screen.findAllByText("Price must be between PKR 1 and PKR 1,000,000 per tonne")).not.toHaveLength(0);
    expect(patched("/api/me/profile")).toHaveLength(0);
  });

  test("a factory must keep at least one residue", async () => {
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    fireEvent.click(screen.getByLabelText("Rice straw"));
    fireEvent.click(save());
    expect((await screen.findAllByText("Choose at least one residue you buy")).length).toBeGreaterThan(0);
    expect(patched("/api/me/profile")).toHaveLength(0);
  });

  test("the spinner stays on for the whole request", async () => {
    const pending = deferred<unknown>();
    vi.mocked(api.PATCH).mockReturnValueOnce(pending.promise as never);
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    type("Factory name", "Bigger Mill");
    fireEvent.click(save());
    await waitFor(() => expect(save()).toHaveAttribute("aria-busy", "true"));
    expect(screen.getByLabelText("Factory name")).toBeDisabled();
    await act(async () => pending.resolve(ok(factoryProfile())));
    expect(await screen.findByText("Saved.")).toBeInTheDocument(); // the toast comes only after the answer
  });

  test("a refusal from the API is shown on the field it names", async () => {
    vi.mocked(api.PATCH).mockResolvedValueOnce(
      fail("That phone number is already linked to another account", 409, [
        { field: "phone", message: "That phone number is already linked to another account", code: "phone_taken" },
      ]),
    );
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    type("Your name", "Owner Two");
    fireEvent.click(save());
    expect((await screen.findAllByText("That phone number is already linked to another account")).length).toBeGreaterThan(0);
  });

  test("Reset puts every field back", async () => {
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    type("Factory name", "Changed");
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByLabelText("Factory name")).toHaveValue("Green Mill");
    expect(save()).toBeDisabled();
  });

  test("every text field stops at its limit", async () => {
    renderAt("/settings", signedIn("factory"));
    await screen.findByLabelText("Factory name");
    expect(screen.getByLabelText("Your name")).toHaveAttribute("maxLength", "80");
    expect(screen.getByLabelText("Factory name")).toHaveAttribute("maxLength", "120");
    expect(screen.getByLabelText("Village or area")).toHaveAttribute("maxLength", "80");
    expect(screen.getByLabelText(/Price you pay/)).toHaveAttribute("maxLength", "12");
  });

  test("a load error offers a retry", async () => {
    mockGet({ "/api/me/profile": fail("Server error", 500) as never });
    renderAt("/settings", signedIn("factory"));
    // a server error is retried once before the retry button is offered
    expect(await screen.findByText(/Could not load your details/, {}, { timeout: 4000 })).toBeInTheDocument();
  });
});

describe("Settings: a transporter", () => {
  beforeEach(() => mockGet({ "/api/me/profile": transporterProfile() }));

  test("edits phone and base but sees tier and max load as read-only", async () => {
    renderAt("/settings", signedIn("transporter"));
    expect(await screen.findByLabelText("Phone")).toBeInTheDocument();
    expect(screen.queryByLabelText("Factory name")).not.toBeInTheDocument();
    expect(screen.getByText(/Tier 1, max load 3 t/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Tier")).not.toBeInTheDocument();
  });

  test("a changed base is sent as district and village", async () => {
    vi.mocked(api.PATCH).mockResolvedValueOnce(ok(transporterProfile({ district: "Kasur", village: "Pattoki" })));
    renderAt("/settings", signedIn("transporter"));
    await screen.findByLabelText("Phone");
    fireEvent.change(screen.getByLabelText("District"), { target: { value: "Kasur" } });
    type("Village or area", "Pattoki");
    fireEvent.click(save());
    await waitFor(() => expect(patched("/api/me/profile")).toHaveLength(1));
    expect(patched("/api/me/profile")[0][1]).toEqual({ body: { district: "Kasur", village: "Pattoki" } });
  });

  test("a village that is too short is refused before sending", async () => {
    renderAt("/settings", signedIn("transporter"));
    await screen.findByLabelText("Phone");
    type("Village or area", "x");
    fireEvent.click(save());
    expect((await screen.findAllByText("Village or area must be at least 2 characters")).length).toBeGreaterThan(0);
    expect(patched("/api/me/profile")).toHaveLength(0);
  });
});

describe("where the details are reachable", () => {
  test("factory and transporter dashboards link to them", async () => {
    mockGet({});
    renderAt("/factory", signedIn("factory"));
    expect(await screen.findByRole("link", { name: /Edit my factory/ })).toHaveAttribute("href", "/settings");
  });

  test("the transporter dashboard links to them too", async () => {
    mockGet({});
    renderAt("/transporter", signedIn("transporter"));
    expect(await screen.findByRole("link", { name: /Edit my details/ })).toHaveAttribute("href", "/settings");
  });

  test("a pending account can fix its details while it waits", async () => {
    mockGet({ "/api/me/profile": transporterProfile({ status: "pending", transporter: { tier: 1, max_tonnes: 3, approved: false } }) });
    vi.mocked(api.PATCH).mockResolvedValueOnce(ok(transporterProfile({ display_name: "Truck Company" })));
    renderAt("/pending", { status: "pending", user: me("transporter", { status: "pending" }) });
    fireEvent.click(screen.getByRole("button", { name: "Edit my details" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(await within(dialog).findByLabelText("Your name"), { target: { value: "Truck Company" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patched("/api/me/profile")).toHaveLength(1));
  });
});

describe("admin: People", () => {
  const person = (over: Record<string, unknown> = {}) => ({
    uid: "t-1", email: "truck@x.pk", role: "transporter", status: "active", display_name: "Truck Co",
    phone: "+923009990001", created_at: "2026-10-16T08:00:00Z", details: { phone: "+923009990001", tier: 1, max_tonnes: 3 },
    ...over,
  });

  test("lists everyone with their role and status", async () => {
    mockGet({ "/api/users": [person(), person({ uid: "f-1", role: "farmer", display_name: "Fatima", details: {} })] });
    renderAt("/admin", signedIn("admin"));
    const people = await screen.findByRole("region", { name: "People" });
    expect(await within(people).findByText("Truck Co")).toBeInTheDocument();
    expect(within(people).getByText("Fatima")).toBeInTheDocument();
    expect(within(people).getByText(/tier 1, 3 t/)).toBeInTheDocument();
  });

  test("searching and filtering ask the API", async () => {
    mockGet({ "/api/users": [person()] });
    renderAt("/admin", signedIn("admin"));
    const people = await screen.findByRole("region", { name: "People" });
    fireEvent.change(within(people).getByLabelText("Search by name or email"), { target: { value: "truck" } });
    fireEvent.change(within(people).getByLabelText("Role"), { target: { value: "transporter" } });
    fireEvent.click(within(people).getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(vi.mocked(api.GET).mock.calls.some(
        (c) => c[0] === "/api/users" && JSON.stringify(c[1]).includes('"q":"truck"') && JSON.stringify(c[1]).includes('"role":"transporter"'),
      )).toBe(true),
    );
  });

  test("the search box stops at 80 characters", async () => {
    mockGet({ "/api/users": [person()] });
    renderAt("/admin", signedIn("admin"));
    const people = await screen.findByRole("region", { name: "People" });
    expect(within(people).getByLabelText("Search by name or email")).toHaveAttribute("maxLength", "80");
  });

  test("editing a transporter changes the tier and sends only that", async () => {
    mockGet({
      "/api/users": [person()],
      "/api/users/{uid}/profile": transporterProfile({ uid: "t-1" }),
    });
    vi.mocked(api.PATCH).mockResolvedValueOnce(ok(transporterProfile({ uid: "t-1", transporter: { tier: 3, max_tonnes: 15, approved: true } })));
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Edit Truck Co" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(await within(dialog).findByLabelText("Tier"), { target: { value: "3" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patched("/api/users/{uid}/profile")).toHaveLength(1));
    expect(patched("/api/users/{uid}/profile")[0][1]).toEqual({
      params: { path: { uid: "t-1" } },
      body: { transporter: { tier: 3 } },
    });
  });

  test("a max load above 100 is refused before sending", async () => {
    mockGet({ "/api/users": [person()], "/api/users/{uid}/profile": transporterProfile({ uid: "t-1" }) });
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Edit Truck Co" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(await within(dialog).findByLabelText("Max load (tonnes)"), { target: { value: "150" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect((await within(dialog).findAllByText("Max load must be more than 0 and at most 100 tonnes")).length).toBeGreaterThan(0);
    expect(patched("/api/users/{uid}/profile")).toHaveLength(0);
  });
});

describe("admin: edit a lot", () => {
  const lot = (over: Record<string, unknown> = {}) => ({
    id: "lot-1", farmer_id: "f1", farmer_name: "Fatima Bibi", farmer_phone: "+923008880099",
    residue_type: "rice_straw", residue_label: "Rice straw", quantity_tonnes: 2.5,
    village: "Raiwind", district: "Lahore", place_match: "exact", lat: 31, lon: 74, status: "assigned",
    factory_name: "Green Mill", quoted_price_per_tonne: 400000, farmer_share_bps: 7000,
    est_farmer_payout: 70000, pickup_from: "2026-10-20T01:00:00Z", pickup_to: "2026-10-20T07:00:00Z",
    job_id: "job-1", job_state: "created", created_at: "2026-10-16T08:00:00Z", ...over,
  });

  test("an unfunded lot can be edited and the new factory is announced", async () => {
    mockGet({ "/api/lots": [lot()] });
    vi.mocked(api.PATCH).mockResolvedValueOnce(ok({ ...lot({ quantity_tonnes: 4, factory_name: "Big Mill" }), override_dropped: true }));
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Edit lot of Fatima Bibi" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/Quantity/)).toHaveValue(2.5);
    fireEvent.change(within(dialog).getByLabelText(/Quantity/), { target: { value: "4" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patched("/api/lots/{lot_id}")).toHaveLength(1));
    expect(patched("/api/lots/{lot_id}")[0][1]).toEqual({
      params: { path: { lot_id: "lot-1" } },
      body: { quantity_tonnes: 4 },
    });
    expect(await screen.findByText(/now goes to Big Mill/)).toBeInTheDocument();
    expect(screen.getByText(/manual factory choice was replaced/)).toBeInTheDocument();
  });

  test("a funded lot is locked", async () => {
    mockGet({ "/api/lots": [lot({ job_state: "funded" })] });
    renderAt("/admin", signedIn("admin"));
    const button = await screen.findByRole("button", { name: "Edit lot of Fatima Bibi" });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Locked");
  });

  test("a quantity over 100 tonnes is refused before sending", async () => {
    mockGet({ "/api/lots": [lot()] });
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Edit lot of Fatima Bibi" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Quantity/), { target: { value: "101" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect((await within(dialog).findAllByText("Quantity must be more than 0 and at most 100 tonnes")).length).toBeGreaterThan(0);
    expect(patched("/api/lots/{lot_id}")).toHaveLength(0);
  });

  test("the API's refusal for a funded lot is shown", async () => {
    mockGet({ "/api/lots": [lot()] });
    vi.mocked(api.PATCH).mockResolvedValueOnce(fail("This lot is already funded and can no longer be changed", 409));
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Edit lot of Fatima Bibi" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Quantity/), { target: { value: "3" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("This lot is already funded and can no longer be changed")).toBeInTheDocument();
  });
});
