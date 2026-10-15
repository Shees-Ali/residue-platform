import {
  PHONE_HELP,
  PRICE_HELP,
  QUANTITY_HELP,
  addDays,
  todayPkt,
  validateLot,
  validatePickupDate,
  validateQuantity,
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

describe("report residue form", () => {
  const today = "2026-10-16";
  const ok = {
    residueType: "rice_straw", quantity: "2.5", pickupDate: "2026-10-17", pickupPart: "morning",
    district: "Lahore", village: "Raiwind",
  };

  test("dates are compared in Pakistan time and counted in days", () => {
    expect(todayPkt(new Date("2026-10-15T20:30:00Z"))).toBe("2026-10-16"); // already after midnight in PKT
    expect(addDays("2026-10-30", 5)).toBe("2026-11-04");
  });

  test("quantity", () => {
    expect(validateQuantity("")).toBe("Quantity is required");
    for (const bad of ["0", "-1", "100.5", "abc"]) expect(validateQuantity(bad)).toBe(QUANTITY_HELP);
    expect(validateQuantity("2.555")).toBe("Quantity can have at most 2 decimals");
    for (const good of ["0.01", "2", "2.5", "100"]) expect(validateQuantity(good)).toBeUndefined();
  });

  test("pickup date: today to 60 days ahead", () => {
    expect(validatePickupDate("", today)).toBe("Pickup date is required");
    expect(validatePickupDate("2026-10-15", today)).toBe("Pickup date cannot be in the past");
    expect(validatePickupDate("2027-01-01", today)).toBe("Pickup date must be within 60 days");
    expect(validatePickupDate("soon", today)).toBe("Pickup date must be a real date, like 2026-10-20");
    expect(validatePickupDate("2026-10-16", today)).toBeUndefined();
    expect(validatePickupDate("2026-12-15", today)).toBeUndefined();
  });

  test("a good form has no errors", () => {
    expect(validateLot(ok, { today })).toEqual({});
  });

  test("every bad field is reported at once, with the API field names", () => {
    const errors = validateLot(
      { ...ok, residueType: "", quantity: "", pickupDate: "2020-01-01", pickupPart: "night", district: "", village: " " },
      { today },
    );
    expect(Object.keys(errors).sort()).toEqual([
      "district", "pickup_date", "pickup_part", "quantity_tonnes", "residue_type", "village",
    ]);
  });

  test("the admin entry also checks the farmer phone and name", () => {
    const errors = validateLot({ ...ok, farmerPhone: "nope", farmerName: "x".repeat(81) }, { admin: true, today });
    expect(errors.farmer_phone).toBe(PHONE_HELP);
    expect(errors.farmer_name).toBe("Name must be at most 80 characters");
    expect(validateLot({ ...ok, farmerPhone: "03001234567" }, { admin: true, today })).toEqual({});
  });
});
