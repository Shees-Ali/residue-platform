import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { PhotoError, uploadPhoto } from "@/api/photos";
import { LocationError, getPosition } from "@/lib/geo";
import { useLocationTracker } from "@/lib/useLocationTracker";
import { fail, mockGet, ok, posted } from "@/test/mockApi";
import { me, renderAt, renderWithProviders, signedIn } from "@/test/renderApp";

// The camera, GPS and the upload are the browser's; here they are controlled by each test.
vi.mock("@/lib/geo", async (orig) => ({ ...(await orig<typeof import("@/lib/geo")>()), getPosition: vi.fn() }));
vi.mock("@/api/photos", async (orig) => ({ ...(await orig<typeof import("@/api/photos")>()), uploadPhoto: vi.fn() }));
vi.mock("./JobMap", () => ({
  JobMap: (p: { path?: unknown[]; truck?: { lat: number } | null }) => (
    <div data-testid="map">points:{p.path?.length ?? 0} truck:{p.truck ? p.truck.lat : "none"}</div>
  ),
}));

const photo = { id: "p1", kind: "delivery", weight_kg: 2450, url: "/api/dev-upload/jobs/j/delivery/a.jpg", created_at: "2026-10-16T08:00:00Z" };
const job = (over: Record<string, unknown> = {}) => ({
  id: "job-1", lot_id: "lot-1", factory_id: "f1", factory_name: "Green Mill", transporter_id: "t1",
  transporter_name: "Truck One", state: "accepted", residue_type: "rice_straw", quantity_tonnes: 2.5,
  village: "Raiwind", district: "Lahore", pickup_lat: 31.4, pickup_lon: 74.4, factory_lat: 31.5, factory_lon: 74.3,
  farmer_name: null, farmer_phone: null, quoted_price_per_tonne: 1_000_000_000, farmer_share_bps: 7000,
  est_weight_kg: 2500, final_weight_kg: null, escrow_amount: 2_500_000_000, est_farmer_payout: 1_750_000_000,
  est_transporter_payout: 500_000_000, rejection_reason: null, photos: [], offers_exhausted: false,
  created_at: "2026-10-16T08:00:00Z", ...over,
});
const jpeg = (size = 1000, type = "image/jpeg") => new File([new Uint8Array(size)], "load.jpg", { type });
const here = { lat: 31.41, lon: 74.39, accuracy_m: 15 };

beforeEach(() => {
  vi.mocked(getPosition).mockResolvedValue(here);
  vi.mocked(uploadPhoto).mockResolvedValue("jobs/job-1/pickup/abc.jpg");
  Object.defineProperty(URL, "createObjectURL", { value: () => "blob:preview", configurable: true });
});

const chooseFile = (file: File) =>
  fireEvent.change(screen.getByLabelText(/Photo of the load/), { target: { files: [file] } });

describe("transporter: record pickup and delivery", () => {
  const start = (j = job()) => {
    mockGet({ "/api/jobs": [j], "/api/ledger/mine": [] });
    renderAt("/transporter", signedIn("transporter"));
  };

  test("pickup sends the photo path, the weight and the position, in that order", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "picked_up" })));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.change(within(dialog).getByLabelText(/Weight loaded/), { target: { value: "2400" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/pickup")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/pickup")[0][1].body).toEqual({
      photo_path: "jobs/job-1/pickup/abc.jpg", weight_kg: 2400, ...here,
    });
    expect(vi.mocked(getPosition).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(uploadPhoto).mock.invocationCallOrder[0],
    );
    expect(await screen.findByText(/Pickup recorded/)).toBeInTheDocument();
  });

  test("a missing photo and a bad weight are explained and nothing is sent", async () => {
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Weight loaded/), { target: { value: "12.5" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect(await screen.findAllByText("Add a photo (JPEG, PNG or WebP, up to 5 MB)")).not.toHaveLength(0);
    expect(screen.getAllByText("Weight must be a whole number of kilograms between 1 and 100,000").length).toBeGreaterThan(0);
    expect(getPosition).not.toHaveBeenCalled();
    expect(posted("/api/jobs/{job_id}/pickup")).toHaveLength(0);
  });

  test("a wrong file type or a file over 5 MB is refused before anything uploads", async () => {
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg(10, "application/pdf"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect((await screen.findAllByText(/Add a photo \(JPEG, PNG or WebP/)).length).toBeGreaterThan(0);
    chooseFile(jpeg(5 * 1024 * 1024 + 1));
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect((await screen.findAllByText("Photo must be 5 MB or smaller")).length).toBeGreaterThan(0);
    expect(uploadPhoto).not.toHaveBeenCalled();
  });

  test("a far-off weight only warns", async () => {
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Weight loaded/), { target: { value: "5000" } });
    expect(within(dialog).getByText(/far from the estimated 2500 kg/)).toBeInTheDocument();
  });

  test("denied location stops the step with the exact message", async () => {
    vi.mocked(getPosition).mockRejectedValue(new LocationError("Allow location access to record this step"));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect((await within(dialog).findAllByText("Allow location access to record this step")).length).toBeGreaterThan(0);
    expect(uploadPhoto).not.toHaveBeenCalled();
    expect(posted("/api/jobs/{job_id}/pickup")).toHaveLength(0);
  });

  test("a failed upload is shown under the photo", async () => {
    vi.mocked(uploadPhoto).mockRejectedValue(new PhotoError("The photo could not be uploaded. Check your connection and try again."));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect((await within(dialog).findAllByText(/could not be uploaded/)).length).toBeGreaterThan(0);
    expect(posted("/api/jobs/{job_id}/pickup")).toHaveLength(0);
  });

  test("the API field errors land on the photo and the weight", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(
      fail("Fix 2 fields", 422, [
        { field: "photo_path", message: "Upload the photo first", code: "not_uploaded" },
        { field: "weight_kg", message: "Weight must be a whole number of kilograms between 1 and 100,000", code: "x" },
      ]),
    );
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    expect(await within(dialog).findByText("Upload the photo first")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Photo of the load")).toHaveAttribute("aria-invalid", "true");
  });

  test("the button spins through location, upload and save", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Record pickup" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.click(within(dialog).getByRole("button", { name: "Record pickup" }));
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Record pickup" })).toHaveAttribute("aria-busy", "true"));
    expect(await within(dialog).findByText("Saving…")).toBeInTheDocument();
    finish(ok(job({ state: "picked_up" })));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  test("a picked-up load offers the delivery step", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "delivered" })));
    start(job({ state: "picked_up" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record delivery" }));
    const dialog = await screen.findByRole("dialog");
    chooseFile(jpeg());
    fireEvent.click(within(dialog).getByRole("button", { name: "Record delivery" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/deliver")).toHaveLength(1));
  });
});

describe("location sharing", () => {
  function Probe({ active }: { active: boolean }) {
    const { status, problem } = useLocationTracker("job-1", active);
    return <p>{status}|{problem}</p>;
  }
  const fix = (lat: number) => ({ coords: { latitude: lat, longitude: 74.4, accuracy: 10 } });
  let onFix: (p: unknown) => void;
  let onError: (e: { code: number }) => void;
  const clearWatch = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    clearWatch.mockClear();
    vi.stubGlobal("navigator", {
      geolocation: {
        watchPosition: vi.fn((ok: (p: unknown) => void, err: (e: { code: number }) => void) => {
          onFix = ok;
          onError = err;
          return 7;
        }),
        clearWatch,
      },
    });
    vi.mocked(api.POST).mockResolvedValue(ok({ recorded: true }));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  test("sends a position at once, then at most every 15 seconds", () => {
    render(<Probe active />);
    act(() => onFix(fix(31.1)));
    expect(posted("/api/jobs/{job_id}/location")).toHaveLength(1);
    expect(posted("/api/jobs/{job_id}/location")[0][1].body).toEqual({ lat: 31.1, lon: 74.4, accuracy_m: 10 });
    act(() => {
      vi.advanceTimersByTime(5_000);
      onFix(fix(31.2));
    });
    expect(posted("/api/jobs/{job_id}/location")).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(11_000);
      onFix(fix(31.3));
    });
    expect(posted("/api/jobs/{job_id}/location")).toHaveLength(2);
    expect(screen.getByText(/^sharing/)).toBeInTheDocument();
  });

  test("blocked location is reported and a finished job stops the watch", () => {
    const { rerender } = render(<Probe active />);
    act(() => onError({ code: 1 }));
    expect(screen.getByText(/^blocked\|Allow location access to record this step/)).toBeInTheDocument();
    rerender(<Probe active={false} />);
    expect(clearWatch).toHaveBeenCalledWith(7);
    expect(screen.getByText(/^off/)).toBeInTheDocument();
  });

  test("a browser with no location support stays off", () => {
    vi.stubGlobal("navigator", {});
    render(<Probe active />);
    expect(screen.getByText(/^off/)).toBeInTheDocument();
  });
});

describe("factory: weighbridge", () => {
  const start = (extra: Record<string, unknown> = {}) => {
    mockGet({ "/api/jobs": [job({ state: "delivered", photos: [photo], ...extra })] });
    renderAt("/factory", signedIn("factory"));
  };

  test("shows the delivered load with the transporter photo and weight", async () => {
    start();
    expect(await screen.findByText(/The transporter reports 2450 kg/)).toBeInTheDocument();
    expect(screen.getByAltText("delivery photo")).toHaveAttribute("src", "/api/dev-upload/jobs/j/delivery/a.jpg");
  });

  test("confirming checks the weight, then sends the final weight", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "confirmed", final_weight_kg: 2480 })));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Confirm weight" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Weight on the weighbridge/), { target: { value: "0" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm weight" }));
    expect((await within(dialog).findAllByText("Weight must be a whole number of kilograms between 1 and 100,000")).length).toBeGreaterThan(0);
    expect(posted("/api/jobs/{job_id}/confirm")).toHaveLength(0);
    fireEvent.change(within(dialog).getByLabelText(/Weight on the weighbridge/), { target: { value: "2480" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm weight" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/confirm")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/confirm")[0][1].body).toEqual({ accept: true, final_weight_kg: 2480, reason: "" });
    expect(await screen.findByText(/The farmer is asked to confirm/)).toBeInTheDocument();
  });

  test("rejecting needs a real reason", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(job({ state: "rejected" })));
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Reject lot" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "ab" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reject lot" }));
    expect((await within(dialog).findAllByText("Give a reason of at least 3 characters")).length).toBeGreaterThan(0);
    fireEvent.change(within(dialog).getByLabelText("Reason"), { target: { value: "Too wet" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reject lot" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/confirm")).toHaveLength(1));
    expect(posted("/api/jobs/{job_id}/confirm")[0][1].body).toEqual({ accept: false, reason: "Too wet" });
  });

  test("the grade estimate shows its disclaimer; when it is not set up the factory is told so", async () => {
    vi.mocked(api.POST)
      .mockResolvedValueOnce(fail("The AI grader is not set up", 503))
      .mockResolvedValueOnce(
        ok({ photo_id: "x", is_estimate: true, grade: { residue_type: "rice_straw", moisture_band: "dry", contamination_flags: ["soil"], confidence: 0.82, disclaimer: "Visual estimate only; weighbridge confirmation required." } }),
      );
    start();
    fireEvent.click(await screen.findByRole("button", { name: "Estimate grade" }));
    expect(await screen.findByText(/not set up on this server/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Estimate grade" }));
    expect(await screen.findByText(/Dry, 82% sure, flags: soil/)).toBeInTheDocument();
    expect(screen.getByText(/weighbridge confirmation required/)).toBeInTheDocument();
  });

  test("a weighbridge photo is uploaded before the estimate", async () => {
    vi.mocked(uploadPhoto).mockResolvedValue("jobs/job-1/weighbridge/w.jpg");
    vi.mocked(api.POST).mockResolvedValueOnce(
      ok({ photo_id: "x", is_estimate: true, grade: { residue_type: "rice_straw", moisture_band: "medium", contamination_flags: [], confidence: 0.5, disclaimer: "d" } }),
    );
    start();
    fireEvent.change(await screen.findByLabelText(/Weighbridge photo/), { target: { files: [jpeg()] } });
    fireEvent.click(screen.getByRole("button", { name: "Estimate grade" }));
    await waitFor(() => expect(posted("/api/jobs/{job_id}/grade")).toHaveLength(1));
    expect(uploadPhoto).toHaveBeenCalledWith("job-1", "weighbridge", expect.any(File));
    expect(posted("/api/jobs/{job_id}/grade")[0][1].body).toEqual({ photo_path: "jobs/job-1/weighbridge/w.jpg" });
  });

  test("an admin looking at the page cannot confirm", async () => {
    mockGet({ "/api/jobs": [job({ state: "delivered" })] });
    renderAt("/factory", signedIn("admin"));
    expect(await screen.findByText("Only the factory can confirm the weight.")).toBeInTheDocument();
  });
});

describe("maps", () => {
  const track = {
    job_id: "job-1", state: "picked_up", pickup: { lat: 31.4, lon: 74.4, name: "Raiwind" },
    factory: { lat: 31.5, lon: 74.3, name: "Green Mill" },
    points: [
      { kind: "pickup", lat: 31.4, lon: 74.4, at: "2026-10-16T08:00:00Z", distance_from_target_m: 30_000 },
      { kind: "ping", lat: 31.45, lon: 74.35, at: new Date().toISOString() },
    ],
    last: { kind: "ping", lat: 31.45, lon: 74.35, at: new Date().toISOString() },
    heading_to: "factory", distance_to_target_km: 8.3, eta_minutes: 13, pickup_off_site_m: 30_000, delivery_off_site_m: null,
  };

  test("the admin sees every load on the road and its map", async () => {
    mockGet({
      "/api/jobs": [], "/api/tracking/active": [{ ...track, residue_type: "rice_straw", quantity_tonnes: 2.5, village: "Raiwind", factory_name: "Green Mill" }],
      "/api/jobs/{job_id}/track": track,
    });
    renderAt("/admin", signedIn("admin"));
    const section = await screen.findByRole("region", { name: "Live map" });
    expect(await within(section).findByTestId("map")).toHaveTextContent("points:2 truck:31.45");
    expect(within(section).getAllByText(/About 13 min and 8.3 km to the factory/).length).toBeGreaterThan(0);
    expect(within(section).getByText("Pickup recorded 30 km from the farm")).toBeInTheDocument();
  });

  test("an empty road says so", async () => {
    mockGet({ "/api/jobs": [], "/api/tracking/active": [] });
    renderAt("/admin", signedIn("admin"));
    expect(await screen.findByText("No load is on the road right now.")).toBeInTheDocument();
  });

  test("the factory can follow one of its loads", async () => {
    mockGet({ "/api/jobs": [job({ state: "picked_up" })], "/api/jobs/{job_id}/track": track });
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Track this load" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByTestId("map")).toBeInTheDocument();
    expect(within(dialog).getByText(/Last seen/)).toBeInTheDocument();
  });

  test("a map that fails to load offers a retry", async () => {
    mockGet({ "/api/jobs": [job({ state: "picked_up" })], "/api/jobs/{job_id}/track": fail("down", 403) });
    renderAt("/factory", signedIn("factory"));
    fireEvent.click(await screen.findByRole("button", { name: "Track this load" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

test("the helpers behind the dialogs", () => {
  renderWithProviders(<p>unused</p>);
  expect(me("farmer").role).toBe("farmer");
});
