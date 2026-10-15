import { useId, useState } from "react";
import {
  COUNTRIES,
  DEFAULT_COUNTRY,
  clean,
  exampleNational,
  flag,
  formatTyping,
  phoneProblem,
  splitE164,
  toE164,
  type CountryCode,
} from "@/lib/phone";
import { LIMITS } from "@/lib/validation";

export interface PhoneState {
  country: CountryCode;
  text: string;
  valid: boolean;
}

interface Props {
  label: string;
  /** The number as +923001234567 when valid, "" otherwise. */
  value: string;
  onChange: (e164: string, state: PhoneState) => void;
  /** A message from the surrounding form; this input's own country-specific message wins. */
  error?: string;
  hint?: string;
  disabled?: boolean;
  defaultCountry?: CountryCode;
}

/** A phone input with a country picker. It formats as you type, accepts a pasted +number or a
 * local one, checks the number against that country's rules, and reports E.164 (or "") upward. */
export function PhoneInput({ label, value, onChange, error, hint, disabled, defaultCountry = DEFAULT_COUNTRY }: Props) {
  const id = useId();
  const noteId = `${id}-note`;
  const start = splitE164(value);
  const [country, setCountry] = useState<CountryCode>(start?.country ?? defaultCountry);
  const [text, setText] = useState(start?.text ?? "");
  const [problem, setProblem] = useState<string | undefined>();

  const emit = (nextText: string, nextCountry: CountryCode) => {
    const e164 = toE164(nextText, nextCountry);
    onChange(e164 ?? "", { country: nextCountry, text: nextText, valid: Boolean(e164) });
  };

  function type(raw: string) {
    const shown = formatTyping(raw, country);
    setText(shown.text);
    setCountry(shown.country); // a pasted +number switches the picker to its country
    setProblem(undefined);
    emit(shown.text, shown.country);
  }

  function pick(code: CountryCode) {
    setCountry(code);
    const digits = clean(text);
    const next = digits.startsWith("+") ? "" : formatTyping(digits, code).text; // a typed +number belongs to its own country
    setText(next);
    setProblem(undefined);
    emit(next, code);
  }

  const shown = problem ?? error;
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <div className="phone-input">
        <select
          aria-label="Country code"
          value={country}
          disabled={disabled}
          onChange={(e) => pick(e.target.value as CountryCode)}
        >
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {flag(c.code)} {c.name} (+{c.dial})
            </option>
          ))}
        </select>
        <input
          id={id}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          value={text}
          maxLength={LIMITS.phoneText.max}
          disabled={disabled}
          placeholder={exampleNational(country)}
          aria-invalid={shown ? true : undefined}
          aria-describedby={shown || hint ? noteId : undefined}
          onChange={(e) => type(e.target.value)}
          onBlur={() => setProblem(text ? phoneProblem(text, country) : undefined)}
        />
      </div>
      {(shown || hint) && (
        <p id={noteId} className={shown ? "field-error" : "field-hint"}>
          {shown ?? hint}
        </p>
      )}
    </div>
  );
}
