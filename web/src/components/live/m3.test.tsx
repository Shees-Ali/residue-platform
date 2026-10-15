import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { fail, mockGet, ok, posted } from "@/test/mockApi";
import { renderAt, signedIn } from "@/test/renderApp";

const job = (over: Record<string, unknown> = {}) => ({
  id: "job-1", lot_id: "lot-1", factory_id: "f1", factory_name: "Green Mill", transporter_id: "t1",
  transporter_name: "Truck One", state: "confirmed", residue_type: "rice_straw", quantity_tonnes: 2.5,
  village: "Raiwind", district: "Lahore", pickup_lat: 31.4, pickup_lon: 74.4, factory_lat: 31.5, factory_lon: 74.3,
  farmer_name: null, farmer_phone: null, quoted_price_per_tonne: 1_000_000_000, farmer_share_bps: 7000,
  est_weight_kg: 2500, final_weight_kg: 2480, escrow_amount: 2_500_000_000, est_farmer_payout: 1_736_000_000,
  est_transporter_payout: 496_000_000, rejection_reason: null, photos: [], offers_exhausted: false,
  created_at: "2026-10-16T08:00:00Z", ...over,
});

describe("farmer: confirm the weight and payment", () => {
  const start = () => {
    mockGet({ "/api/jobs": [job()], "/api/lots": [], "/api/ledger/mine": [] });
    renderAt("/farmer", signedIn("farmer"));
  };

  test("the farmer sees what the factory weighed and what they will be paid", async () => {
    start();
    expect(await screen.findByText("Confirm your weight and payment")).toBeInTheDocument();
    expect(screen.getByText(/Green Mill weighed 2480 kg \(you reported 2500 kg\)/)).toBeInTheDocument();
    expect(screen.getByText("PKR 17,360,000")).toBeInTheDocument();
  });

  test("yes releases the payment and says how much", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok({ job_id: "job-1", state: "settled", farmer_amount: 1_736_000_000 }));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Yes, pay me" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/verify")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/verify")[0][1].body).toEqual({ confirmed: true, note: "" });
    expect(posted("/api/jobs/{job_id}/verify")[0][1].params?.path).toEqual({ job_id: "job-1" });
    expect(await screen.findByText(/PKR 17,360,000 has been released to you/)).toBeInTheDocument();
  });

  test("a dispute needs a reason, then freezes the money", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok({ job_id: "job-1", state: "disputed", farmer_amount: null }));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Dispute" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("What is wrong?"), { target: { value: "no" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send dispute" }));
    expect((await within(dialog).findAllByText("Tell us what is wrong (at least 3 characters)")).length).toBeGreaterThan(0);
    expect(posted("/api/jobs/{job_id}/verify")).toHaveLength(0);
    fireEvent.change(within(dialog).getByLabelText("What is wrong?"), { target: { value: "The weight is too low" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send dispute" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/verify")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/verify")[0][1].body).toEqual({ confirmed: false, note: "The weight is too low" });
    expect(await screen.findByText(/money stays frozen/)).toBeInTheDocument();
  });

  test("a refusal from the API is shown", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(fail("The job is 'settled', not waiting for your confirmation", 409));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Yes, pay me" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not waiting for your confirmation");
  });

  test("the button spins while the answer is sent", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Yes, pay me" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Yes, pay me" })).toHaveAttribute("aria-busy", "true"));
    expect(screen.getByRole("button", { name: "Dispute" })).toBeDisabled();
    finish(ok({ job_id: "job-1", state: "settled", farmer_amount: 1 }));
  });

  test("nothing to confirm shows no confirmation section; payments are listed", async () => {
    mockGet({
      "/api/jobs": [],
      "/api/ledger/mine": [
        { job_id: "abcdef1234", state: "settled", status: "released", amount: 1_736_000_000 },
        { job_id: "zzzzzz9999", state: "accepted", status: "pending", amount: 900_000_000 },
      ],
    });
    renderAt("/farmer", signedIn("farmer"));
    expect(await screen.findByText("Your payments")).toBeInTheDocument();
    expect(screen.queryByText("Confirm your weight and payment")).not.toBeInTheDocument();
    expect(screen.getByText("Paid")).toBeInTheDocument();
    expect(screen.getByText("Expected")).toBeInTheDocument();
  });
});

describe("admin: money, impact and the queue", () => {
  const admin = () => renderAt("/admin", signedIn("admin"));
  const entry = (i: number, kind = "escrow_in") => ({
    id: `e${i}`, job_id: `job${i}abcdef`, order_id: null, kind, amount: 2_500_000_000, created_at: "2026-10-16T08:00:00Z",
  });

  test("the overview numbers come from the API", async () => {
    mockGet({
      "/api/stats": {
        farmers: 12, factories: 4, transporters: 6, transporters_waiting_approval: 2, live_jobs: 3,
        jobs_settled: 5, orders: 7, tonnes_diverted: 12.5, escrow_held: 4_000_000_000, open_escalations: 1,
      },
    });
    admin();
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getByText("12.5 t")).toBeInTheDocument();
    expect(screen.getByText("PKR 40,000,000")).toBeInTheDocument();
    expect(screen.getByText("2 awaiting approval")).toBeInTheDocument();
  });

  test("a balanced ledger says so and the table names each movement", async () => {
    mockGet({
      "/api/ledger": [entry(1), entry(2, "release_farmer")],
      "/api/ledger/check": { balanced: true, jobs_checked: 4, orders_checked: 1, unbalanced_jobs: [], unbalanced_orders: [], held_in_escrow: 0, totals: {} },
    });
    admin();
    const section = await screen.findByRole("region", { name: "Ledger" });
    expect(await within(section).findByText("Ledger balanced")).toBeInTheDocument();
    expect(within(section).getByText("Escrow in")).toBeInTheDocument();
    expect(within(section).getByText("Paid to farmer")).toBeInTheDocument();
    expect(within(section).getAllByText("PKR 25,000,000")).toHaveLength(2);
  });

  test("an unbalanced ledger is flagged", async () => {
    mockGet({
      "/api/ledger/check": { balanced: false, jobs_checked: 4, orders_checked: 0, unbalanced_jobs: ["j1"], unbalanced_orders: [], held_in_escrow: 0, totals: {} },
    });
    admin();
    expect(await screen.findByText("Ledger out of balance (1)")).toBeInTheDocument();
  });

  test("the ledger pages through older entries", async () => {
    const page = Array.from({ length: 15 }, (_, i) => entry(i));
    mockGet({ "/api/ledger": page });
    admin();
    const section = await screen.findByRole("region", { name: "Ledger" });
    fireEvent.click(await within(section).findByRole("button", { name: /Older/ }));
    await waitFor(() =>
      expect(vi.mocked(api.GET).mock.calls.some((c) => c[0] === "/api/ledger" && (c[1] as { params: { query: { offset: number } } }).params.query.offset === 15)).toBe(true),
    );
    expect(within(section).getByRole("button", { name: /Newer/ })).toBeEnabled();
  });

  test("impact shows the tonnes and the settled records", async () => {
    mockGet({
      "/api/impact": {
        tonnes_diverted: 3.4, jobs_settled: 2,
        records: [{ job_id: "j", lot_id: "l", farmer_id: "f", farmer_name: "Fatima Bibi", village: "Raiwind", district: "Lahore", weight_kg: 2480, settled_at: "2026-10-16T09:00:00Z" }],
      },
    });
    admin();
    const section = await screen.findByRole("region", { name: "Impact" });
    expect(await within(section).findByText("3.4 tonnes")).toBeInTheDocument();
    expect(within(section).getByText("Fatima Bibi")).toBeInTheDocument();
  });

  test("the queue lists phone and web disputes and resolves one", async () => {
    mockGet({
      "/api/escalations": [
        { id: "esc1", call_id: null, job_id: "job-1", summary: "Farmer disputed the weight", transcript: "", status: "open", farmer_phone: "+923008880099", created_at: "2026-10-16T09:00:00Z" },
        { id: "esc2", call_id: "c1", job_id: null, summary: "Caller is upset", transcript: "", status: "open", farmer_phone: null, created_at: "2026-10-16T09:05:00Z" },
      ],
    });
    vi.mocked(api.POST).mockResolvedValueOnce(ok(undefined, 204));
    admin();
    const queue = await screen.findByRole("region", { name: "Escalations" });
    expect(await within(queue).findByText(/\+923008880099 .* web dispute/)).toBeInTheDocument();
    expect(within(queue).getByText(/Unknown caller .* phone call/)).toBeInTheDocument();
    fireEvent.click(within(queue).getAllByRole("button", { name: "Resolve" })[0]);
    await waitFor(() => expect(posted("/api/escalations/{escalation_id}/resolve")).toHaveLength(1));
    expect(posted("/api/escalations/{escalation_id}/resolve")[0][1].params?.path).toEqual({ escalation_id: "esc1" });
    expect(await screen.findByText("Marked as resolved.")).toBeInTheDocument();
  });

  test("an empty queue says so, and a failed ledger offers a retry", async () => {
    mockGet({ "/api/ledger": fail("down", 403) });
    admin();
    expect(await screen.findByText("Nothing needs a person right now.")).toBeInTheDocument();
    const section = await screen.findByRole("region", { name: "Ledger" });
    expect(await within(section).findByRole("button", { name: "Try again" }, { timeout: 4000 })).toBeInTheDocument();
  });
});

describe("factory: money for a load", () => {
  test("the factory sees what went in and out for one job", async () => {
    mockGet({
      "/api/jobs": [job({ state: "settled" })],
      "/api/jobs/{job_id}/ledger": [
        { id: "a", job_id: "job-1", order_id: null, kind: "escrow_in", amount: 2_500_000_000, created_at: "2026-10-16T08:00:00Z" },
        { id: "b", job_id: "job-1", order_id: null, kind: "refund", amount: 20_000_000, created_at: "2026-10-16T09:00:00Z" },
      ],
    });
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Money" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Escrow in")).toBeInTheDocument();
    expect(within(dialog).getByText("Refunded to factory")).toBeInTheDocument();
    expect(screen.getByText("Finished loads")).toBeInTheDocument();
  });

  test("a load waiting on the farmer says so", async () => {
    mockGet({ "/api/jobs": [job()] });
    renderAt("/factory", signedIn("factory"));
    expect(await screen.findByText(/Waiting for the farmer to confirm the payment/)).toBeInTheDocument();
  });
});
