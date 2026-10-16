import { errorMessage } from "@/api/errors";
import { canAccess, homeFor } from "@/lib/auth";

describe("canAccess", () => {
  test("admin pages are admin only", () => {
    expect(canAccess("/admin", "admin")).toBe(true);
    for (const r of ["buyer", "factory", "transporter", "farmer"] as const) {
      expect(canAccess("/admin", r)).toBe(false);
    }
    expect(canAccess("/admin", undefined)).toBe(false);
  });
  test("each role reaches its own page", () => {
    expect(canAccess("/farmer", "farmer")).toBe(true);
    expect(canAccess("/transporter", "transporter")).toBe(true);
    expect(canAccess("/factory", "factory")).toBe(true);
    expect(canAccess("/market", "buyer")).toBe(true);
  });
  test("the marketplace is public; buying is not a page rule", () => {
    expect(canAccess("/market", "buyer")).toBe(true);
    expect(canAccess("/market", "farmer")).toBe(true);
    expect(canAccess("/market", "transporter")).toBe(true);
    expect(canAccess("/market", undefined)).toBe(true); // a signed-out visitor may browse
  });
  test("the call widget is admin only for now", () => {
    expect(canAccess("/call", "buyer")).toBe(false);
    expect(canAccess("/call", "admin")).toBe(true);
  });
  test("every role has a home it may open", () => {
    for (const r of ["admin", "transporter", "factory", "buyer", "farmer"] as const) {
      expect(canAccess(homeFor(r), r)).toBe(true);
    }
  });
});

describe("errorMessage", () => {
  test("reads FastAPI detail strings, objects and validation lists", () => {
    expect(errorMessage({ detail: "Nope" })).toBe("Nope");
    expect(errorMessage({ detail: { code: "x", message: "Wait for approval" } })).toBe(
      "Wait for approval",
    );
    expect(errorMessage({ detail: [{ msg: "field required" }, { msg: "too short" }] })).toBe(
      "field required; too short",
    );
    expect(errorMessage({ error: "bad", message: "Fix the district" })).toBe("Fix the district");
  });
  test("falls back for anything else", () => {
    expect(errorMessage(undefined, "fallback")).toBe("fallback");
    expect(errorMessage({}, "fallback")).toBe("fallback");
  });
});
