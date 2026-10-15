import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { PhoneInput } from "./phone-input";

function Harness({ initial = "", error, onValue }: { initial?: string; error?: string; onValue?: (v: string) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <PhoneInput
      label="Phone"
      value={value}
      error={error}
      onChange={(v) => {
        setValue(v);
        onValue?.(v);
      }}
    />
  );
}

const input = () => screen.getByLabelText("Phone") as HTMLInputElement;
const picker = () => screen.getByLabelText("Country code") as HTMLSelectElement;
const type = (v: string) => fireEvent.change(input(), { target: { value: v } });

test("starts on Pakistan with an example of what to type", () => {
  render(<Harness />);
  expect(picker().value).toBe("PK");
  expect(input().placeholder).toMatch(/^03\d\d \d{7}$/);
});

test("a local number formats as you type and reports E.164", () => {
  const seen: string[] = [];
  render(<Harness onValue={(v) => seen.push(v)} />);
  type("03131087151");
  expect(input().value).toBe("0313 1087151");
  expect(seen.at(-1)).toBe("+923131087151");
});

test("a number that is not finished reports nothing yet", () => {
  const seen: string[] = [];
  render(<Harness onValue={(v) => seen.push(v)} />);
  type("0313108");
  expect(seen.at(-1)).toBe("");
});

test("pasting a +number with invisible marks switches the country and formats it", () => {
  const seen: string[] = [];
  render(<Harness onValue={(v) => seen.push(v)} />);
  fireEvent.change(picker(), { target: { value: "US" } });
  type("‎+92 313 1087151‬");
  expect(picker().value).toBe("PK");
  expect(input().value).toBe("+92 313 1087151");
  expect(seen.at(-1)).toBe("+923131087151");
});

test("another country uses its own format and rules", () => {
  const seen: string[] = [];
  render(<Harness onValue={(v) => seen.push(v)} />);
  fireEvent.change(picker(), { target: { value: "US" } });
  type("4155552671");
  expect(input().value).toBe("(415) 555-2671");
  expect(seen.at(-1)).toBe("+14155552671");
});

test("changing the country re-reads the digits for that country", () => {
  const seen: string[] = [];
  render(<Harness onValue={(v) => seen.push(v)} />);
  type("3131087151");
  expect(seen.at(-1)).toBe("+923131087151");
  fireEvent.change(picker(), { target: { value: "IN" } });
  expect(seen.at(-1)).toBe(""); // the same digits are not an Indian mobile number
});

test("leaving the field with a wrong number names the country and gives an example", () => {
  render(<Harness />);
  type("0350 1234567");
  fireEvent.blur(input());
  expect(screen.getByText(/That is not a valid Pakistan mobile number, like 03/)).toBeInTheDocument();
  expect(input()).toHaveAttribute("aria-invalid", "true");
  type("0313 1087151");
  expect(screen.queryByText(/not a valid Pakistan/)).not.toBeInTheDocument(); // cleared as it is fixed
});

test("the form's own error shows when the input has nothing more specific", () => {
  render(<Harness error="Verify your phone number to continue" />);
  expect(screen.getByText("Verify your phone number to continue")).toBeInTheDocument();
});

test("a stored number shows in its own country's format", () => {
  render(<Harness initial="+14155552671" />);
  expect(picker().value).toBe("US");
  expect(input().value).toBe("(415) 555-2671");
});

test("can be disabled", () => {
  render(<PhoneInput label="Phone" value="" onChange={() => {}} disabled />);
  expect(input()).toBeDisabled();
  expect(picker()).toBeDisabled();
});
