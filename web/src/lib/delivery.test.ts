import { api } from "@/api/client";
import { PhotoError, uploadPhoto } from "@/api/photos";
import { auth } from "@/lib/firebase";
import { LocationError, getPosition, locationMessage } from "./geo";
import { ago, arrivalText, offSiteNotes } from "./tracking";
import {
  PHOTO_HELP,
  WEIGHT_HELP,
  accuracyWarning,
  validatePhotoFile,
  validateWeightKg,
  weightWarning,
} from "./validation";

describe("photo and weight rules", () => {
  test("only JPEG, PNG or WebP, not empty, at most 5 MB", () => {
    expect(validatePhotoFile(null)).toBe(PHOTO_HELP);
    expect(validatePhotoFile({ type: "image/gif", size: 10 })).toBe(PHOTO_HELP);
    expect(validatePhotoFile({ type: "application/pdf", size: 10 })).toBe(PHOTO_HELP);
    expect(validatePhotoFile({ type: "image/png", size: 0 })).toBe("The photo file is empty");
    expect(validatePhotoFile({ type: "image/webp", size: 5 * 1024 * 1024 + 1 })).toBe("Photo must be 5 MB or smaller");
    for (const type of ["image/jpeg", "image/png", "image/webp"]) {
      expect(validatePhotoFile({ type, size: 5 * 1024 * 1024 })).toBeUndefined();
    }
  });

  test("weight is whole kilograms from 1 to 100,000", () => {
    expect(validateWeightKg("")).toBe("Weight is required");
    for (const bad of ["0", "-3", "100001", "12.5", "abc", "1e3"]) expect(validateWeightKg(bad)).toBe(WEIGHT_HELP);
    for (const good of ["1", "2400", "100000"]) expect(validateWeightKg(good)).toBeUndefined();
  });

  test("a far weight and a vague location only warn", () => {
    expect(weightWarning("2400", 2500)).toBeUndefined();
    expect(weightWarning("5000", 2500)).toBe("That is far from the estimated 2500 kg. Check the weight.");
    expect(weightWarning("abc", 2500)).toBeUndefined();
    expect(accuracyWarning(20)).toBeUndefined();
    expect(accuracyWarning(null)).toBeUndefined();
    expect(accuracyWarning(1200)).toBe("Your location is only accurate to 1200 m. Move outdoors and try again.");
  });
});

describe("reading the phone location", () => {
  afterEach(() => vi.unstubAllGlobals());

  test("a fix is returned as lat, lon and accuracy", async () => {
    vi.stubGlobal("navigator", {
      geolocation: { getCurrentPosition: (ok: (p: unknown) => void) => ok({ coords: { latitude: 31.4, longitude: 74.3, accuracy: 9 } }) },
    });
    await expect(getPosition()).resolves.toEqual({ lat: 31.4, lon: 74.3, accuracy_m: 9 });
  });

  test.each([
    [1, "Allow location access to record this step"],
    [2, "Could not find your location. Turn on GPS and try again."],
    [3, "Could not get your location in time. Try again outdoors or check GPS."],
  ])("error code %i becomes a clear message", async (code, message) => {
    vi.stubGlobal("navigator", {
      geolocation: { getCurrentPosition: (_ok: unknown, err: (e: { code: number }) => void) => err({ code }) },
    });
    await expect(getPosition()).rejects.toThrow(LocationError);
    await expect(getPosition()).rejects.toThrow(message);
    expect(locationMessage(code)).toBe(message);
  });

  test("a browser without location support says so", async () => {
    vi.stubGlobal("navigator", {});
    await expect(getPosition()).rejects.toThrow("This browser cannot share your location.");
  });
});

describe("the tracking words", () => {
  const now = Date.parse("2026-10-16T10:00:00Z");
  test("how fresh a position is", () => {
    expect(ago("2026-10-16T09:59:30Z", now)).toBe("30 s ago");
    expect(ago("2026-10-16T09:50:00Z", now)).toBe("10 min ago");
    expect(ago("2026-10-16T07:00:00Z", now)).toBe("3 h ago");
  });

  test("the arrival sentence is honest about what it knows", () => {
    expect(arrivalText({})).toBe("No position shared yet");
    expect(arrivalText({ last: { at: new Date().toISOString() } })).toMatch(/^Last seen/);
    const text = arrivalText({
      heading_to: "factory", distance_to_target_km: 8.3, eta_minutes: 13, last: { at: new Date().toISOString() },
    });
    expect(text).toMatch(/About 13 min and 8.3 km to the factory \(straight line\)/);
    expect(arrivalText({ heading_to: "pickup", distance_to_target_km: 2, eta_minutes: 3, last: { at: new Date().toISOString() } })).toMatch(/to the farm/);
  });

  test("a reading far from where it should be is badged", () => {
    expect(offSiteNotes({ pickup_off_site_m: 30_000, delivery_off_site_m: 90_000 })).toEqual([
      "Pickup recorded 30 km from the farm",
      "Delivery recorded 90 km from the factory",
    ]);
    expect(offSiteNotes({ pickup_off_site_m: 800, delivery_off_site_m: null })).toEqual([]);
  });
});

describe("uploading a photo", () => {
  const file = () => new File([new Uint8Array(50)], "p.jpg", { type: "image/jpeg" });
  const slot = (url: string) =>
    ({ data: { path: "jobs/j/pickup/a.jpg", upload_url: url, method: "PUT" }, response: { status: 200 } }) as never;

  afterEach(() => {
    vi.unstubAllGlobals();
    (auth as unknown as { currentUser: unknown }).currentUser = null;
  });

  test("a local upload address gets the sign-in token and returns the path", async () => {
    (auth as unknown as { currentUser: unknown }).currentUser = { getIdToken: async () => "tok" };
    vi.mocked(api.POST).mockResolvedValueOnce(slot("/api/dev-upload/jobs/j/pickup/a.jpg"));
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(uploadPhoto("j", "pickup", file())).resolves.toBe("jobs/j/pickup/a.jpg");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/dev-upload/jobs/j/pickup/a.jpg");
    expect(init.method).toBe("PUT");
    expect(init.headers).toMatchObject({ "Content-Type": "image/jpeg", Authorization: "Bearer tok" });
  });

  test("a Cloud Storage address never gets the sign-in token", async () => {
    (auth as unknown as { currentUser: unknown }).currentUser = { getIdToken: async () => "tok" };
    vi.mocked(api.POST).mockResolvedValueOnce(slot("https://storage.googleapis.com/bucket/x?sig=1"));
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await uploadPhoto("j", "pickup", file());
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty("Authorization");
  });

  test("a bad file is refused before any request", async () => {
    await expect(uploadPhoto("j", "pickup", new File(["x"], "a.pdf", { type: "application/pdf" }))).rejects.toThrow(PhotoError);
    expect(api.POST).not.toHaveBeenCalled();
  });

  test("a network failure and a refusal both become readable errors", async () => {
    vi.mocked(api.POST).mockResolvedValue(slot("/api/dev-upload/jobs/j/pickup/a.jpg"));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(uploadPhoto("j", "pickup", file())).rejects.toThrow(/could not be uploaded. Check your connection/);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Photo must be 5 MB or smaller" }), { status: 422 })),
    );
    await expect(uploadPhoto("j", "pickup", file())).rejects.toThrow("Photo must be 5 MB or smaller");
  });
});
