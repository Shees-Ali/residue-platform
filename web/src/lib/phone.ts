// Phone numbers: the country decides what a valid number looks like. Built on libphonenumber, the
// same rules as the API (which uses the Python port), mobile numbers only because we send SMS.
import {
  AsYouType,
  getCountries,
  getCountryCallingCode,
  getExampleNumber,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js/mobile";
import examples from "libphonenumber-js/mobile/examples";

export type { CountryCode };

export const DEFAULT_COUNTRY: CountryCode = "PK";
export const PHONE_HELP = "Phone must include the country code, like +923001234567";

const regionNames =
  typeof Intl !== "undefined" && "DisplayNames" in Intl ? new Intl.DisplayNames(["en"], { type: "region" }) : null;

export const countryName = (code: CountryCode): string => regionNames?.of(code) ?? code;

/** The flag emoji for a country (some systems show the two letters instead). */
export const flag = (code: CountryCode): string =>
  String.fromCodePoint(...[...code].map((c) => 127397 + c.charCodeAt(0)));

export interface Country {
  code: CountryCode;
  name: string;
  dial: string; // calling code, without the plus
}

/** Every country, Pakistan first, the rest by name. */
export const COUNTRIES: Country[] = getCountries()
  .map((code) => ({ code, name: countryName(code), dial: getCountryCallingCode(code) }))
  .sort((a, b) =>
    a.code === DEFAULT_COUNTRY ? -1 : b.code === DEFAULT_COUNTRY ? 1 : a.name.localeCompare(b.name),
  );

/** Keep only digits and plus signs: spaces, dashes, brackets and the invisible direction marks that
 * a copied number often carries all go. A leading 00 means +. */
export function clean(raw: string): string {
  const v = raw.replace(/[^\d+]/g, "");
  return v.startsWith("00") ? `+${v.slice(2)}` : v;
}

/** A sample mobile number for a country, written the way people there write it. */
export function exampleNational(country: CountryCode): string {
  return getExampleNumber(country, examples)?.formatNational() ?? "";
}

/** E.164 (+923001234567) for a valid mobile number, or null.
 *
 * `country` is how to read a number that has no country code (the one picked in the input). With no
 * country, a number needs its + or a leading 0 (read as Pakistani), the same as the API. */
export function toE164(raw: string, country?: CountryCode): string | null {
  const v = clean(raw);
  const explicit = v.startsWith("+");
  const read = explicit ? undefined : (country ?? (v.startsWith("0") ? DEFAULT_COUNTRY : undefined));
  if (!explicit && !read) return null;
  const parsed = parsePhoneNumberFromString(v, read);
  return parsed?.isValid() ? parsed.number : null;
}

/** Why a number cannot be used, naming the country; undefined when it is fine or nothing was typed. */
export function phoneProblem(raw: string, country?: CountryCode): string | undefined {
  const v = clean(raw);
  if (!v || toE164(v, country)) return undefined;
  const explicit = v.startsWith("+");
  const parsed = parsePhoneNumberFromString(v, explicit ? undefined : (country ?? DEFAULT_COUNTRY));
  const where = parsed?.country ?? country;
  if (!explicit && !country && !v.startsWith("0")) return PHONE_HELP; // no country code at all
  if (where) {
    const example = exampleNational(where);
    return `That is not a valid ${countryName(where)} mobile number${example ? `, like ${example}` : ""}`;
  }
  return PHONE_HELP;
}

/** Format what has been typed so far the way that country writes numbers. */
export function formatTyping(raw: string, country: CountryCode): { text: string; country: CountryCode } {
  const v = clean(raw);
  if (v.startsWith("+")) {
    const typing = new AsYouType();
    const text = typing.input(v);
    return { text, country: typing.getCountry() ?? country };
  }
  return { text: new AsYouType(country).input(v), country };
}

/** The picker value and the text for a stored E.164 number. */
export function splitE164(e164: string): { country: CountryCode; text: string } | null {
  const parsed = e164 ? parsePhoneNumberFromString(e164) : undefined;
  return parsed?.country ? { country: parsed.country, text: parsed.formatNational() } : null;
}
