import { fireEvent, screen, waitFor } from "@testing-library/react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { api } from "@/api/client";
import { ApiError } from "@/api/query";
import { me, renderAt } from "@/test/renderApp";

vi.mock("firebase/auth", async (orig) => ({
  ...(await orig<typeof import("firebase/auth")>()),
  signInWithEmailAndPassword: vi.fn().mockRejectedValue({ code: "auth/invalid-credential" }),
}));

const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("login form", () => {
  const login = () => renderAt("/login", { status: "signedOut" });

  test("empty fields show an explicit message under each input and nothing is sent", async () => {
    login();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter your email address")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Email")).toHaveFocus(); // the first bad field
    expect(screen.getByRole("alert")).toHaveTextContent("Fix 2 fields"); // the toast summary
    expect(signInWithEmailAndPassword).not.toHaveBeenCalled();
  });

  test("a malformed email is explained on blur and clears as it is fixed", () => {
    login();
    type("Email", "nope");
    fireEvent.blur(screen.getByLabelText("Email"));
    expect(screen.getByText(/valid email address/)).toBeInTheDocument();
    type("Email", "nope@x.pk");
    expect(screen.queryByText(/valid email address/)).not.toBeInTheDocument();
  });

  test("valid input is sent, and a Firebase refusal is toasted", async () => {
    login();
    type("Email", "a@b.pk");
    type("Password", "whatever");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(signInWithEmailAndPassword).toHaveBeenCalled());
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
  });
});

describe("account step", () => {
  const account = () => renderAt("/signup", { status: "signedOut" });

  test("a weak password and a mismatch are each called out", async () => {
    account();
    type("Email", "a@b.pk");
    type("Password", "weak");
    type("Confirm password", "other");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Use at least 8 characters with a letter and a number")).toBeInTheDocument();
    expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
  });
});

describe("role step", () => {
  const start = () => renderAt("/signup", { status: "needsRegistration", email: "a@b.pk", name: "" });
  const pick = (r: RegExp) => fireEvent.click(screen.getByRole("radio", { name: r }));

  test("every missing field of a factory is marked at once", async () => {
    start();
    pick(/Factory/);
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    expect(await screen.findByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Factory name is required")).toBeInTheDocument();
    expect(screen.getByText("Price per tonne is required")).toBeInTheDocument();
    expect(screen.getByText("Choose at least one residue you buy")).toBeInTheDocument();
    expect(screen.getByText("Village or area is required")).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  test("an out-of-range price is explained", async () => {
    start();
    pick(/Factory/);
    type("Price you pay per tonne (PKR)", "5000000");
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    expect(
      await screen.findByText("Price must be between PKR 1 and PKR 1,000,000 per tonne"),
    ).toBeInTheDocument();
  });

  test("a typed local phone is sent in international form", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce({
      data: me("transporter", { status: "pending" }),
      response: { status: 201 },
    } as never);
    start();
    pick(/Transporter/);
    type("Your name", "Truck Co");
    type("Village or area", "Raiwind");
    type(/Phone/, "0300 1234567");
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(vi.mocked(api.POST).mock.calls[0][1]).toMatchObject({
      body: { role: "transporter", phone: "+923001234567", village: "Raiwind", district: "Lahore" },
    });
  });

  test("field errors from the API land on the same inputs", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce({
      error: {
        detail: "That phone number is already linked to another account",
        errors: [
          { field: "phone", message: "That phone number is already linked to another account", code: "phone_taken" },
        ],
      },
      response: { status: 409 },
    } as never);
    start();
    pick(/Transporter/);
    type("Your name", "Truck Co");
    type("Village or area", "Raiwind");
    type(/Phone/, "+923001234567");
    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    const msg = "That phone number is already linked to another account";
    expect(await screen.findAllByText(msg)).not.toHaveLength(0);
    expect(screen.getByLabelText(/Phone/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(msg); // and the toast
  });

  test("an ApiError carries the fields the API named", () => {
    const e = new ApiError("x", 422, { display_name: "Name is required" });
    expect(e.fields.display_name).toBe("Name is required");
  });
});
