import {
  COUNTRIES,
  PHONE_HELP,
  clean,
  countryName,
  exampleNational,
  flag,
  formatTyping,
  phoneProblem,
  splitE164,
  toE164,
} from "./phone";

describe("cleaning a typed or pasted number", () => {
  test.each([
    ["‎+923131087151", "a left-to-right mark"],
    [" ‪+92 313 1087151‬", "direction marks and spaces"],
    ["+92 313 1087151", "non-breaking spaces"],
    ["﻿+923131087151​", "a byte-order mark and a zero-width space"],
    ["(+92) 313-1087151", "brackets and a dash"],
    ["00923131087151", "a 00 in place of the plus"],
  ])("%j keeps only the digits (%s)", (typed) => {
    expect(clean(typed)).toBe("+923131087151");
  });
});

describe("one number, read by its country's rules", () => {
  test.each([
    ["+923131087151", undefined, "+923131087151"],
    ["0313 1087151", undefined, "+923131087151"], // a local Pakistani number
    ["3131087151", "PK", "+923131087151"], // national digits plus the picked country
    ["(415) 555-2671", "US", "+14155552671"],
    ["07400 123456", "GB", "+447400123456"],
    ["+91 98765 43210", undefined, "+919876543210"],
    ["98765 43210", "IN", "+919876543210"],
    ["+971 50 123 4567", undefined, "+971501234567"],
  ])("%s (%s) is %s", (typed, country, expected) => {
    expect(toE164(typed, country as never)).toBe(expected);
  });

  test.each([
    ["", undefined],
    ["abc", undefined],
    ["3131087151", undefined], // no country code and no picked country
    ["+0123456789", undefined],
    ["+92", undefined],
    ["+923501234567", undefined], // 35x is not a Pakistani mobile prefix
    ["313108715", "PK"], // one digit short
    ["31310871511", "PK"], // one digit long
    ["+442071838750x", "PK"], // a UK number is not valid just because it is long enough
  ])("%j (%s) is refused", (typed, country) => {
    expect(toE164(typed, country as never)).toBeNull();
  });

  test("a landline-only prefix is not a mobile number", () => {
    expect(toE164("+924235761234")).toBeNull(); // a Lahore landline
  });
});

describe("the message names the country and gives an example", () => {
  test("a wrong Pakistani number", () => {
    const m = phoneProblem("0350 1234567", "PK");
    expect(m).toMatch(/^That is not a valid Pakistan mobile number, like 03/);
  });

  test("another country is named by its own name and example", () => {
    expect(phoneProblem("123", "US")).toMatch(/not a valid United States mobile number, like \(/);
    expect(phoneProblem("+44 1", undefined)).toMatch(/United Kingdom|PHONE/i);
  });

  test("a number with no country code at all gets the plain instruction", () => {
    expect(phoneProblem("3131087151")).toBe(PHONE_HELP);
  });

  test("nothing typed, or a valid number, is not a problem", () => {
    expect(phoneProblem("", "PK")).toBeUndefined();
    expect(phoneProblem("0313 1087151", "PK")).toBeUndefined();
  });
});

describe("formatting as you type", () => {
  test("a Pakistani local number", () => {
    expect(formatTyping("03131087151", "PK").text).toBe("0313 1087151");
  });

  test("a pasted +number picks its country and formats internationally", () => {
    const r = formatTyping("+923131087151", "US");
    expect(r.country).toBe("PK");
    expect(r.text).toBe("+92 313 1087151");
  });

  test("a US number", () => {
    expect(formatTyping("4155552671", "US").text).toBe("(415) 555-2671");
  });

  test("invisible marks do not get in the way", () => {
    expect(formatTyping("‎03131087151", "PK").text).toBe("0313 1087151");
  });
});

describe("the country list", () => {
  test("Pakistan comes first, the rest by name, each with a dial code and a flag", () => {
    expect(COUNTRIES[0]).toMatchObject({ code: "PK", dial: "92", name: "Pakistan" });
    const rest = COUNTRIES.slice(1).map((c) => c.name);
    expect(rest).toEqual([...rest].sort((a, b) => a.localeCompare(b)));
    expect(COUNTRIES.length).toBeGreaterThan(200);
    expect(flag("PK")).toBe("\u{1F1F5}\u{1F1F0}");
    expect(countryName("US")).toBe("United States");
    expect(exampleNational("PK")).toMatch(/^03\d\d \d{7}$/);
  });

  test("a stored number splits back into its country and national text", () => {
    expect(splitE164("+923131087151")).toEqual({ country: "PK", text: "0313 1087151" });
    expect(splitE164("")).toBeNull();
  });
});
