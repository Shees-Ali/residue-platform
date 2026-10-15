import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { fail, mockGet, ok, posted } from "@/test/mockApi";
import { me, renderAt, signedIn } from "@/test/renderApp";

const inSeconds = (s: number) => new Date(Date.now() + s * 1000).toISOString();

const job = (over: Record<string, unknown> = {}) => ({
  id: "job-1", lot_id: "lot-1", factory_id: "f1", factory_name: "Green Mill", transporter_id: null,
  transporter_name: null, state: "created", residue_type: "rice_straw", quantity_tonnes: 2.5,
  village: "Raiwind", district: "Lahore", pickup_lat: 31.4, pickup_lon: 74.4, factory_lat: 31.5,
  factory_lon: 74.3, farmer_name: null, farmer_phone: null, quoted_price_per_tonne: 1_000_000_000,
  farmer_share_bps: 7000, est_weight_kg: 2500, final_weight_kg: null, escrow_amount: 2_500_000_000,
  est_farmer_payout: 1_750_000_000, est_transporter_payout: 500_000_000, rejection_reason: null,
  photos: [], offers_exhausted: false, created_at: "2026-10-16T08:00:00Z", ...over,
});

const offer = (over: Record<string, unknown> = {}) => ({
  id: "off-1", job_id: "job-1", status: "pending", expires_at: inSeconds(90), payout_amount: 500_000_000,
  est_weight_kg: 2500, residue_type: "rice_straw", village: "Raiwind", pickup_lat: 31.4, pickup_lon: 74.4,
  factory_name: "Green Mill", factory_lat: 31.5, factory_lon: 74.3, ...over,
});

describe("factory: fund escrow", () => {
  test("a matched job shows the escrow and funding it starts dispatch", async () => {
    mockGet({ "/api/jobs": [job()] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "offered" })));
    renderAt("/factory", signedIn("factory"));
    expect(await screen.findByText(/Escrow to fund:/)).toHaveTextContent("PKR 25,000,000");
    fireEvent.click(screen.getByRole("button", { name: "Fund escrow" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/2500 kg at PKR 10,000,000 per tonne/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /^Fund PKR 25,000,000$/ }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/fund")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/fund")[0][1].params?.path).toEqual({ job_id: "job-1" });
    expect(await screen.findByText(/nearest transporter has been offered/)).toBeInTheDocument();
  });

  test("with no transporter available the factory is told what happens next", async () => {
    mockGet({ "/api/jobs": [job()] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "funded" })));
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Fund escrow" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /^Fund PKR/ }));
    expect(await screen.findByText(/No transporter is available yet/)).toBeInTheDocument();
  });

  test("a refusal is shown and the dialog stays open to try again", async () => {
    mockGet({ "/api/jobs": [job()] });
    vi.mocked(api.POST).mockResolvedValueOnce(fail("Job is not in state created", 409));
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Fund escrow" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /^Fund PKR/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Job is not in state created");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  test("the button spins and the dialog locks while the request is in flight", async () => {
    mockGet({ "/api/jobs": [job()] });
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Fund escrow" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^Fund PKR/ }));
    await waitFor(() => expect(within(dialog).getByRole("button", { name: /^Fund PKR/ })).toHaveAttribute("aria-busy", "true"));
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toBeDisabled();
    finish(ok(job({ state: "offered" })));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  test("loads on the road show their stage; an admin cannot fund", async () => {
    mockGet({ "/api/jobs": [job({ id: "j2", state: "accepted", transporter_name: "Truck Co" }), job()] });
    renderAt("/factory", signedIn("admin"));
    expect(await screen.findByText("Truck Co")).toBeInTheDocument();
    expect(screen.getByText("Only the factory can fund this job.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Fund escrow" })).not.toBeInTheDocument();
  });

  test("a failed load offers a retry", async () => {
    mockGet({ "/api/jobs": fail("down", 403) });
    renderAt("/factory", signedIn("factory"));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("transporter: offers", () => {
  const start = () => renderAt("/transporter", signedIn("transporter"));

  test("an open offer shows the countdown, the pay and the haul; a lapsed one is hidden", async () => {
    mockGet({ "/api/offers": [offer(), offer({ id: "old", expires_at: inSeconds(-30), village: "Gone" })] });
    start();
    expect(await screen.findByText(/^1:(29|30)$/)).toBeInTheDocument();
    expect(screen.getByText(/Your pay about/)).toHaveTextContent("PKR 5,000,000");
    expect(screen.getByText(/km to Green Mill/)).toBeInTheDocument();
    expect(screen.queryByText(/Gone/)).not.toBeInTheDocument();
  });

  test("accepting sends the offer and confirms", async () => {
    mockGet({ "/api/offers": [offer()] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "accepted" })));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Accept job" }));
    await waitFor(() => expect(posted("/api/offers/{offer_id}/accept")).toHaveLength(1));
    expect(posted("/api/offers/{offer_id}/accept")[0][1].params?.path).toEqual({ offer_id: "off-1" });
    expect(await screen.findByText(/Job accepted/)).toBeInTheDocument();
  });

  test("losing the race to another transporter is explained", async () => {
    mockGet({ "/api/offers": [offer()] });
    vi.mocked(api.POST).mockResolvedValueOnce(
      fail("This offer is no longer available (expired or already taken)", 409),
    );
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Accept job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no longer available");
  });

  test("passing sends a decline", async () => {
    mockGet({ "/api/offers": [offer()] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(undefined, 204));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Pass" }));
    await waitFor(() => expect(posted("/api/offers/{offer_id}/decline")).toHaveLength(1));
    expect(await screen.findByText(/goes to the next transporter/)).toBeInTheDocument();
  });

  test("while answering, both buttons lock and the clicked one spins", async () => {
    mockGet({ "/api/offers": [offer()] });
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Accept job" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept job" })).toHaveAttribute("aria-busy", "true"));
    expect(screen.getByRole("button", { name: "Pass" })).toBeDisabled();
    finish(ok(job({ state: "accepted" })));
  });

  test("an accepted job shows the farmer contact and the expected pay", async () => {
    mockGet({
      "/api/jobs": [job({ state: "accepted", transporter_id: "t1", farmer_name: "Fatima Bibi", farmer_phone: "+923008880099" })],
      "/api/ledger/mine": [{ job_id: "job-1", state: "accepted", status: "pending", amount: 500_000_000 }],
    });
    start();
    expect(await screen.findByText(/Fatima Bibi · \+923008880099/)).toBeInTheDocument();
    expect(screen.getByText("Payout pending")).toBeInTheDocument();
  });

  test("a paid job says paid", async () => {
    mockGet({
      "/api/jobs": [job({ state: "settled", transporter_id: "t1" })],
      "/api/ledger/mine": [{ job_id: "job-1", state: "settled", status: "released", amount: 480_000_000 }],
    });
    start();
    expect(await screen.findAllByText("Paid")).not.toHaveLength(0);
    expect(screen.getAllByText(/PKR 4,800,000/)).toHaveLength(2); // the stat and the card
  });
});

describe("admin: dispatch", () => {
  const start = () => renderAt("/admin", { status: "ready", user: me("admin") });

  test("jobs waiting on a transporter are listed and an exhausted one says so", async () => {
    mockGet({
      "/api/jobs": [job({ id: "a", state: "offered" }), job({ id: "b", state: "funded", offers_exhausted: true })],
    });
    start();
    const section = await screen.findByRole("region", { name: "Dispatch" });
    expect(await within(section).findByText("Every transporter passed")).toBeInTheDocument();
    expect(within(section).getAllByRole("button", { name: "Offers" })).toHaveLength(2);
  });

  test("moving offers on reports what happened", async () => {
    mockGet({ "/api/jobs": [] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok({ expired: 2, reoffered: 1, exhausted: 1, dispatched: 0 }));
    start();
    fireEvent.click(await screen.findByRole("button", { name: /Move pending offers on now/ }));
    await waitFor(() => expect(posted("/api/dispatch/tick")).toHaveLength(1));
    expect(posted("/api/dispatch/tick")[0][1].body).toEqual({ force: true });
    expect(await screen.findByText(/2 offer\(s\) moved on, 1 sent to the next transporter, 1 ran out/)).toBeInTheDocument();
  });

  test("sending a funded job out again", async () => {
    mockGet({ "/api/jobs": [job({ id: "b", state: "funded", offers_exhausted: true })] });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "offered" })));
    start();
    fireEvent.click(await screen.findByRole("button", { name: /Send out again/ }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/redispatch")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/redispatch")[0][1].params?.path).toEqual({ job_id: "b" });
  });

  test("the ladder dialog lists who was offered the load", async () => {
    mockGet({
      "/api/jobs": [job({ id: "a", state: "offered" })],
      "/api/jobs/{job_id}/offers": [
        { id: "o1", sequence: 1, transporter_id: "t1", transporter_name: "Truck One", transporter_phone: "+9230011", status: "expired", expires_at: inSeconds(-5), payout_amount: 500_000_000 },
        { id: "o2", sequence: 2, transporter_id: "t2", transporter_name: "Truck Two", transporter_phone: "+9230022", status: "pending", expires_at: inSeconds(60), payout_amount: 500_000_000 },
      ],
    });
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Offers" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Truck Two")).toBeInTheDocument();
    expect(within(dialog).getByText("expired")).toBeInTheDocument();
  });

  test("the transporter roster can approve and stop", async () => {
    mockGet({
      "/api/jobs": [],
      "/api/transporters": [
        { id: "t1", user_uid: "u1", display_name: "Truck One", phone: "+9230011", tier: 1, max_tonnes: 3, approved: true, approved_at: "2026-10-01T00:00:00Z", lat: 1, lon: 1 },
        { id: "t2", user_uid: "u2", display_name: "Truck Two", phone: "+9230022", tier: 1, max_tonnes: 3, approved: false, approved_at: null, lat: 1, lon: 1 },
      ],
    });
    vi.mocked(api.POST).mockResolvedValueOnce(ok({}));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(posted("/api/transporters/{transporter_id}/approve")).toHaveLength(1));
    expect(posted("/api/transporters/{transporter_id}/approve")[0][1].body).toEqual({ tier: 1 });
    expect(screen.getByRole("button", { name: "Stop offers" })).toBeInTheDocument();
  });
});
