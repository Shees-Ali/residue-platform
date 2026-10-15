import { RecaptchaVerifier, linkWithPhoneNumber } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { disposeRecaptcha, sendPhoneCode } from "./phone";

// Firebase draws a reCAPTCHA into an element; a second one in the same element throws
// "reCAPTCHA has already been rendered". The rule: one verifier, reused for every send.
const made = vi.hoisted(() => ({
  verifiers: [] as { el: HTMLElement; clear: ReturnType<typeof vi.fn>; render: ReturnType<typeof vi.fn> }[],
}));
vi.mock("firebase/auth", () => ({
  RecaptchaVerifier: vi.fn().mockImplementation((_auth: unknown, el: HTMLElement) => {
    const v = { el, clear: vi.fn(), render: vi.fn().mockResolvedValue(7) };
    made.verifiers.push(v);
    return v;
  }),
  linkWithPhoneNumber: vi.fn(),
}));

const reset = vi.fn();
const sent = { confirm: async () => ({}) };

beforeEach(() => {
  made.verifiers.length = 0;
  reset.mockClear();
  (window as unknown as { grecaptcha: unknown }).grecaptcha = { reset };
  document.body.innerHTML = '<div id="recaptcha-container"></div>';
  (auth as unknown as { currentUser: unknown }).currentUser = { uid: "u" };
  vi.mocked(linkWithPhoneNumber).mockResolvedValue(sent as never);
});
afterEach(() => {
  disposeRecaptcha();
  (auth as unknown as { currentUser: unknown }).currentUser = null;
});

describe("sending the SMS code", () => {
  test("every send uses the same reCAPTCHA instance", async () => {
    await sendPhoneCode("+923131087151", "recaptcha-container");
    await sendPhoneCode("+923131087151", "recaptcha-container");
    await sendPhoneCode("+923131087151", "recaptcha-container");
    expect(RecaptchaVerifier).toHaveBeenCalledTimes(1);
    const used = vi.mocked(linkWithPhoneNumber).mock.calls.map((c) => c[2]);
    expect(used).toHaveLength(3);
    expect(new Set(used).size).toBe(1); // the very same object each time
    expect(made.verifiers[0].clear).not.toHaveBeenCalled();
  });

  test("it is created in the container element itself", async () => {
    await sendPhoneCode("+923131087151", "recaptcha-container");
    expect(made.verifiers[0].el).toBe(document.getElementById("recaptcha-container"));
  });

  test("a failed send resets the challenge and keeps the same instance for the next try", async () => {
    vi.mocked(linkWithPhoneNumber).mockRejectedValueOnce({ code: "auth/invalid-phone-number" });
    await expect(sendPhoneCode("+923131087151", "recaptcha-container")).rejects.toMatchObject({
      code: "auth/invalid-phone-number",
    });
    expect(reset).toHaveBeenCalledWith(7); // the widget was reset...
    await sendPhoneCode("+923131087151", "recaptcha-container");
    expect(RecaptchaVerifier).toHaveBeenCalledTimes(1); // ...not rebuilt
  });

  test("a double click joins the send already running instead of starting a second", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(linkWithPhoneNumber).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    const first = sendPhoneCode("+923131087151", "recaptcha-container");
    const second = sendPhoneCode("+923131087151", "recaptcha-container");
    expect(second).toBe(first);
    finish(sent);
    await first;
    expect(linkWithPhoneNumber).toHaveBeenCalledTimes(1);
  });

  test("if the page element was replaced, the old verifier is removed and a new one is made", async () => {
    await sendPhoneCode("+923131087151", "recaptcha-container");
    document.body.innerHTML = '<div id="recaptcha-container"></div>'; // the panel was left and reopened
    await sendPhoneCode("+923131087151", "recaptcha-container");
    expect(RecaptchaVerifier).toHaveBeenCalledTimes(2);
    expect(made.verifiers[0].clear).toHaveBeenCalled();
    expect(made.verifiers[1].el).toBe(document.getElementById("recaptcha-container"));
  });

  test("disposing clears the widget so a later visit starts clean", async () => {
    await sendPhoneCode("+923131087151", "recaptcha-container");
    document.getElementById("recaptcha-container")!.innerHTML = "<div>widget</div>";
    disposeRecaptcha();
    expect(made.verifiers[0].clear).toHaveBeenCalled();
    expect(document.getElementById("recaptcha-container")!.innerHTML).toBe("");
    await sendPhoneCode("+923131087151", "recaptcha-container");
    expect(RecaptchaVerifier).toHaveBeenCalledTimes(2);
  });

  test("it needs a signed-in account and the reCAPTCHA area on the page", async () => {
    document.body.innerHTML = "";
    await expect(sendPhoneCode("+923131087151", "recaptcha-container")).rejects.toThrow(/reCAPTCHA area is missing/);
    document.body.innerHTML = '<div id="recaptcha-container"></div>';
    (auth as unknown as { currentUser: unknown }).currentUser = null;
    await expect(sendPhoneCode("+923131087151", "recaptcha-container")).rejects.toThrow("Sign in first");
  });

  test("disposing with nothing drawn is harmless", () => {
    expect(() => disposeRecaptcha()).not.toThrow();
  });
});
