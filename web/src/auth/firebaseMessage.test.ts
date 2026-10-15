import { firebaseMessage } from "./AuthProvider";

test.each([
  ["auth/operation-not-allowed", /Authentication, Sign-in method, and enable it/],
  ["auth/operation-not-allowed", /SMS region policy/],
  ["auth/billing-not-enabled", /need billing/],
  ["auth/unauthorized-domain", /Authorized domains/],
  ["auth/invalid-phone-number", /country code|like \+923001234567/],
  ["auth/code-expired", /expired/],
  ["auth/popup-closed-by-user", /cancelled/],
])("%s says what to do", (code, expected) => {
  expect(firebaseMessage({ code })).toMatch(expected);
});

test("a replaced popup says nothing, and an unknown code falls back to the error text", () => {
  expect(firebaseMessage({ code: "auth/cancelled-popup-request" })).toBe("");
  expect(firebaseMessage(new Error("Something odd"))).toBe("Something odd");
  expect(firebaseMessage(undefined)).toBe("Something went wrong. Try again.");
});
