import {
  PHONE_HELP,
  PRICE_HELP,
  normalizePhone,
  pkrToPaisa,
  summarize,
  validateConfirm,
  validateEmail,
  validateLoginPassword,
  validateNewPassword,
  validatePrice,
  validateProfile,
  validateText,
  type ProfileValues,
} from "./validation";

describe("phone", () => {
  test.each([
    ["+923001234567", "+923001234567"],
    ["+92 300 123-4567", "+923001234567"],
    ["(+92) 300 1234567", "+923001234567"],
    ["03001234567", "+923001234567"],
    ["00923001234567", "+923001234567"],
  ])("%s becomes %s", (typed, clean) => expect(normalizePhone(typed)).toBe(clean));

  test.each(["", "abc", "12345", "+0123456789", "+92", "+9230012345678901"])("%j is refused", (typed) =>
    expect(normalizePhone(typed)).toBeNull(),
  );
});

describe("email and passwords", () => {
  test("email", () => {
    expect(validateEmail("")).toBe("Enter your email address");
    expect(validateEmail("nope")).toMatch(/valid email/);
    expect(validateEmail("a@b")).toMatch(/valid email/);
    expect(validateEmail(" a@b.pk ")).toBeUndefined();
  });
  test("a new password needs length, a letter and a number", () => {
    for (const bad of ["short1", "allletters", "12345678", ""]) {
      expect(validateNewPassword(bad)).toMatch(/8 characters/);
    }
    expect(validateNewPassword("longenough1")).toBeUndefined();
    expect(validateNewPassword("a1" + "x".repeat(200))).toMatch(/8 characters/);
  });
  test("login only needs a password to be present", () => {
    expect(validateLoginPassword("")).toBe("Enter your password");
    expect(validateLoginPassword("x")).toBeUndefined();
  });
  test("confirmation must match", () => {
    expect(validateConfirm("a", "b")).toBe("Passwords do not match");
    expect(validateConfirm("a", "a")).toBeUndefined();
  });
});

describe("text and price", () => {
  test("trimmed length limits name the field", () => {
    expect(validateText("  ", "Name", 2, 80)).toBe("Name is required");
    expect(validateText("A", "Name", 2, 80)).toBe("Name must be at least 2 characters");
    expect(validateText("x".repeat(81), "Name", 2, 80)).toBe("Name must be at most 80 characters");
    expect(validateText(" Ali ", "Name", 2, 80)).toBeUndefined();
  });
  test("price is PKR 1 to PKR 1,000,000 and converts to paisa", () => {
    expect(validatePrice("")).toBe("Price per tonne is required");
    expect(validatePrice("abc")).toBe("Price per tonne must be a number");
    expect(validatePrice("0")).toBe(PRICE_HELP);
    expect(validatePrice("1000001")).toBe(PRICE_HELP);
    expect(validatePrice("1")).toBeUndefined();
    expect(validatePrice("1000000")).toBeUndefined();
    expect(pkrToPaisa("4000")).toBe(400000);
    expect(pkrToPaisa("0.5")).toBe(50);
    expect(pkrToPaisa("")).toBeNull();
  });
});

describe("signup profile", () => {
  const base: ProfileValues = {
    role: "buyer", name: "Bilal", phone: "", district: "Lahore", village: "", factoryName: "",
    price: "", residues: [],
  };
  test("a buyer needs only a name", () => {
    expect(validateProfile(base)).toEqual({});
    expect(validateProfile({ ...base, name: "B" })).toEqual({
      display_name: "Name must be at least 2 characters",
    });
  });
  test("a transporter needs phone and place, all reported together", () => {
    expect(Object.keys(validateProfile({ ...base, role: "transporter" })).sort()).toEqual([
      "phone", "village",
    ]);
    expect(validateProfile({ ...base, role: "transporter", phone: "x", village: "Raiwind" }).phone).toBe(
      PHONE_HELP,
    );
  });
  test("a factory needs name, price, residues and place", () => {
    const errors = validateProfile({ ...base, role: "factory" });
    expect(Object.keys(errors).sort()).toEqual([
      "factory.name", "factory.price_per_tonne", "factory.residues", "village",
    ]);
    const ok = validateProfile({
      ...base, role: "factory", village: "Raiwind", factoryName: "Green Mill", price: "4000",
      residues: ["rice_straw"],
    });
    expect(ok).toEqual({});
  });
  test("the summary is one sentence for one error and a list for several", () => {
    expect(summarize({ a: "Name is required" })).toBe("Name is required");
    expect(summarize({ a: "A bad", b: "B bad" })).toBe("Fix 2 fields: A bad; B bad");
  });
});
