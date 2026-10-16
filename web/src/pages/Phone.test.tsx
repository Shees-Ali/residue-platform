import { fireEvent, screen } from "@testing-library/react";
import { renderAt } from "@/test/renderApp";

const OUT = { status: "signedOut" } as const;

afterEach(() => localStorage.clear());

describe("public phone page", () => {
  test("opens without signing in and asks for the number first", () => {
    renderAt("/phone", OUT);
    expect(screen.getByRole("heading", { name: "Residue line" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save number" })).toBeDisabled();
  });

  test("a number it cannot use keeps the save button off", () => {
    renderAt("/phone", OUT);
    fireEvent.change(screen.getByLabelText("Your mobile number"), { target: { value: "12345" } });
    expect(screen.getByRole("button", { name: "Save number" })).toBeDisabled();
  });

  test("a valid number is remembered and the call screen shows", () => {
    renderAt("/phone", OUT);
    fireEvent.change(screen.getByLabelText("Your mobile number"), { target: { value: "0300 1234567" } });
    fireEvent.click(screen.getByRole("button", { name: "Save number" }));
    expect(screen.getByRole("heading", { name: "Residue agent" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start call" })).toBeInTheDocument();
    expect(localStorage.getItem("residue.phone")).toBe("+923001234567");
  });

  test("a remembered number goes straight to the call screen and can be changed", () => {
    localStorage.setItem("residue.phone", "+923001234567");
    renderAt("/phone", OUT);
    expect(screen.getByRole("button", { name: "Start call" })).toBeInTheDocument();
    expect(screen.getByText(/\+923001234567/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Change number" }));
    expect(screen.getByRole("heading", { name: "Residue line" })).toBeInTheDocument();
  });

  test("the admin call desk still needs a sign-in", () => {
    renderAt("/call", OUT);
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
