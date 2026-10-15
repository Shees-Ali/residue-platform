import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { auth } from "@/lib/firebase";
import { mockGet } from "@/test/mockApi";
import { me, renderAt, signedIn } from "@/test/renderApp";

// The SMS step is Firebase's; here it just succeeds, so we can test what the app does after it.
vi.mock("@/auth/phone", () => ({
  sendPhoneCode: vi.fn(async () => ({ confirm: async () => ({}) })),
  confirmPhoneCode: vi.fn(async () => {}),
  disposeRecaptcha: vi.fn(),
}));

const RESIDUES = [
  { code: "rice_straw", label: "Rice straw" },
  { code: "wheat_straw", label: "Wheat straw" },
];

const lot = (over: Record<string, unknown> = {}) => ({
  id: "lot-1", farmer_id: "f1", farmer_name: "Fatima Bibi", farmer_phone: "+923008880099",
  residue_type: "rice_straw", residue_label: "Rice straw", quantity_tonnes: 2.5,
  village: "Raiwind", district: "Lahore", place_match: "exact", lat: 31, lon: 74, status: "assigned",
  factory_name: "Green Mill", quoted_price_per_tonne: 400000, farmer_share_bps: 7000,
  est_farmer_payout: 70000, pickup_from: "2026-10-20T01:00:00Z", pickup_to: "2026-10-20T07:00:00Z",
  job_id: "job-1", job_state: "created", created_at: "2026-10-16T08:00:00Z", ...over,
});

const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const openForm = async () => {
  fireEvent.click(await screen.findByRole("button", { name: /Report residue/ }));
  return screen.findByRole("dialog");
};
const submitIn = (dialog: HTMLElement) =>
  fireEvent.click(within(dialog).getByRole("button", { name: "Report residue" }));
const posted = (path: string) => vi.mocked(api.POST).mock.calls.filter((c) => c[0] === path);

beforeEach(() => mockGet({ "/api/residue-types": RESIDUES, "/api/districts": ["Lahore", "Kasur"] }));

describe("farmer page", () => {
  test("an unlinked farmer is asked to verify their phone and cannot report", async () => {
    renderAt("/farmer", { status: "ready", user: me("farmer", { farmer_linked: false }) });
    expect(await screen.findByText("Verify your phone to report residue")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Report residue/ })).not.toBeInTheDocument();
  });

  test("verifying the phone links the account and opens the form", async () => {
    (auth as unknown as { currentUser: unknown }).currentUser = { uid: "u-farmer", email: "f@x.pk", displayName: null };
    mockGet({ "/api/me": me("farmer", { farmer_linked: true }), "/api/lots": [] });
    vi.mocked(api.POST).mockResolvedValueOnce({ data: me("farmer", { farmer_linked: true }), response: { status: 200 } } as never);
    renderAt("/farmer", { status: "ready", user: me("farmer", { farmer_linked: false }) });

    fireEvent.change(await screen.findByLabelText(/Your mobile number/), { target: { value: "0300 1234567" } });
    fireEvent.click(screen.getByRole("button", { name: "Send code" }));
    fireEvent.change(await screen.findByLabelText("6-digit code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify code" }));

    await waitFor(() => expect(posted("/api/me/link-phone")).toHaveLength(1));
    expect(await screen.findByRole("button", { name: /Report residue/ })).toBeInTheDocument();
    expect(screen.queryByText("Verify your phone to report residue")).not.toBeInTheDocument();
    (auth as unknown as { currentUser: unknown }).currentUser = null;
  });

  test("a bad phone number is explained before any SMS is sent", async () => {
    renderAt("/farmer", { status: "ready", user: me("farmer", { farmer_linked: false }) });
    fireEvent.change(await screen.findByLabelText(/Your mobile number/), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Send code" }));
    expect(await screen.findAllByText("Phone must include the country code, like +923001234567")).not.toHaveLength(0);
  });

  test("requests show their stage, the matched factory and the expected payout", async () => {
    mockGet({ "/api/lots": [lot(), lot({ id: "lot-2", job_id: null, job_state: null, factory_name: null, est_farmer_payout: null, status: "open", place_match: "district" })] });
    renderAt("/farmer", signedIn("farmer"));
    expect(await screen.findByText("Green Mill")).toBeInTheDocument();
    expect(screen.getByText("Waiting for a factory")).toBeInTheDocument();
    expect(screen.getByText(/You would receive about/)).toBeInTheDocument();
    expect(screen.getByText(/district centre used/)).toBeInTheDocument();
    expect(screen.getByText("Live data")).toBeInTheDocument();
  });

  test("a failed load offers a retry instead of an empty page", async () => {
    mockGet({ "/api/lots": { error: { detail: "Server is down" }, response: { status: 500 } } });
    renderAt("/farmer", signedIn("farmer"));
    // a server error is retried once (after 1 s) before the person is told
    expect(await screen.findByRole("button", { name: "Try again" }, { timeout: 4000 })).toBeInTheDocument();
  });

  test("an empty form names every problem under its field and sends nothing", async () => {
    renderAt("/farmer", signedIn("farmer"));
    const dialog = await openForm();
    type("Pickup date", "2020-01-01");
    submitIn(dialog);
    expect(await screen.findByText("Quantity is required")).toBeInTheDocument();
    expect(screen.getByText("Pickup date cannot be in the past")).toBeInTheDocument();
    expect(screen.getByText("Village or area is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Quantity (tonnes)")).toHaveFocus();
    expect(posted("/api/lots/mine")).toHaveLength(0);
  });

  test.each([
    ["0", "Quantity must be more than 0 and at most 100 tonnes"],
    ["150", "Quantity must be more than 0 and at most 100 tonnes"],
    ["2.555", "Quantity can have at most 2 decimals"],
  ])("a quantity of %s is explained", async (value, message) => {
    renderAt("/farmer", signedIn("farmer"));
    const dialog = await openForm();
    type("Quantity (tonnes)", value);
    type("Village or area", "Raiwind");
    submitIn(dialog);
    expect(await screen.findAllByText(message)).not.toHaveLength(0);
  });

  test("a valid form sends the lot with an idempotency key and says which factory took it", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce({ data: lot(), response: { status: 201 } } as never);
    renderAt("/farmer", signedIn("farmer"));
    const dialog = await openForm();
    type("Quantity (tonnes)", "2.5");
    type("Village or area", "Raiwind");
    submitIn(dialog);
    await waitFor(() => expect(posted("/api/lots/mine")).toHaveLength(1));
    const [, init] = posted("/api/lots/mine")[0] as unknown as [string, { body: Record<string, unknown>; params: { header: Record<string, string> } }];
    expect(init.body).toMatchObject({
      residue_type: "rice_straw", quantity_tonnes: 2.5, pickup_part: "morning", village: "Raiwind", district: "Lahore",
    });
    expect(init.params.header["idempotency-key"]).toBeTruthy();
    expect(await screen.findByText("Request saved. Matched to Green Mill.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  test("the same key is reused when the person fixes an error and sends again", async () => {
    vi.mocked(api.POST)
      .mockResolvedValueOnce({
        error: { detail: "Pickup date cannot be in the past", errors: [{ field: "pickup_date", message: "Pickup date cannot be in the past", code: "pickup_date_in_past" }] },
        response: { status: 422 },
      } as never)
      .mockResolvedValueOnce({ data: lot(), response: { status: 201 } } as never);
    renderAt("/farmer", signedIn("farmer"));
    const dialog = await openForm();
    type("Quantity (tonnes)", "2");
    type("Village or area", "Raiwind");
    submitIn(dialog);
    // the server disagrees about the date: its message lands under that field
    expect(await screen.findAllByText("Pickup date cannot be in the past")).not.toHaveLength(0);
    expect(screen.getByLabelText("Pickup date")).toHaveAttribute("aria-invalid", "true");
    submitIn(dialog);
    await waitFor(() => expect(posted("/api/lots/mine")).toHaveLength(2));
    const keys = posted("/api/lots/mine").map((c) => (c[1] as unknown as { params: { header: Record<string, string> } }).params.header["idempotency-key"]);
    expect(keys[0]).toBe(keys[1]);
  });

  test("while the request is in flight the button spins and the form is locked", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    renderAt("/farmer", signedIn("farmer"));
    const dialog = await openForm();
    type("Quantity (tonnes)", "2");
    type("Village or area", "Raiwind");
    submitIn(dialog);
    const button = await within(dialog).findByRole("button", { name: "Report residue" });
    await waitFor(() => expect(button).toHaveAttribute("aria-busy", "true"));
    expect(screen.getByLabelText("Quantity (tonnes)")).toBeDisabled();
    finish({ data: lot(), response: { status: 201 } });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("admin lots", () => {
  test("the admin sees every lot with the farmer and the stage", async () => {
    mockGet({ "/api/lots": [lot()], "/api/users": [] });
    renderAt("/admin", signedIn("admin"));
    const section = await screen.findByRole("region", { name: "Reported lots" });
    expect(await within(section).findByText("Fatima Bibi")).toBeInTheDocument();
    expect(within(section).getByText("+923008880099")).toBeInTheDocument();
    expect(within(section).getByText("Green Mill")).toBeInTheDocument();
  });

  test("adding a lot for a farmer checks the phone, then sends it cleaned", async () => {
    mockGet({ "/api/lots": [], "/api/users": [], "/api/residue-types": RESIDUES, "/api/districts": ["Lahore"] });
    vi.mocked(api.POST).mockResolvedValueOnce({ data: { lot_id: "x" }, response: { status: 201 } } as never);
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: /Add a lot for a farmer/ }));
    const dialog = await screen.findByRole("dialog");
    type(/Farmer phone/, "call me");
    type("Quantity (tonnes)", "3");
    type("Village or area", "Raiwind");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save lot" }));
    expect(await screen.findAllByText("Phone must include the country code, like +923001234567")).not.toHaveLength(0);
    expect(posted("/api/lots")).toHaveLength(0);

    type(/Farmer phone/, "0300 5550101");
    type(/Farmer name/, "Walk-in Farmer");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save lot" }));
    await waitFor(() => expect(posted("/api/lots")).toHaveLength(1));
    expect((posted("/api/lots")[0][1] as unknown as { body: Record<string, unknown> }).body).toMatchObject({
      farmer_phone: "+923005550101", farmer_name: "Walk-in Farmer", quantity_tonnes: 3,
    });
    expect(await screen.findByText(/Lot saved/)).toBeInTheDocument();
  });

  test("the ranking dialog lists factories and checks the override reason", async () => {
    mockGet({
      "/api/lots": [lot()], "/api/users": [],
      "/api/lots/{lot_id}/ranking": [
        { factory_id: "a", factory_name: "Green Mill", rank: 1, score: 1.2, distance_km: 4.5, price_per_tonne: 400000, chosen: true, override_reason: null },
        { factory_id: "b", factory_name: "Blue Mill", rank: 2, score: 1.0, distance_km: 9.1, price_per_tonne: 380000, chosen: false, override_reason: null },
      ],
    });
    vi.mocked(api.POST).mockResolvedValueOnce({ data: {}, response: { status: 200 } } as never);
    renderAt("/admin", signedIn("admin"));
    fireEvent.click(await screen.findByRole("button", { name: "Ranking" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Blue Mill", { selector: "td" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Override" }));
    expect(await screen.findAllByText("Choose the factory to assign")).not.toHaveLength(0);
    expect(posted("/api/lots/{lot_id}/override")).toHaveLength(0);

    fireEvent.change(within(dialog).getByLabelText("Assign a different factory"), { target: { value: "b" } });
    fireEvent.change(within(dialog).getByLabelText("Reason (logged)"), { target: { value: "Cheaper haul" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Override" }));
    await waitFor(() => expect(posted("/api/lots/{lot_id}/override")).toHaveLength(1));
    expect((posted("/api/lots/{lot_id}/override")[0][1] as unknown as { body: unknown }).body).toEqual({
      factory_id: "b", reason: "Cheaper haul",
    });
  });
});
