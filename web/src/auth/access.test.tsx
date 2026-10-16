import { fireEvent, screen, within } from "@testing-library/react";
import { me, renderAt, signedIn } from "@/test/renderApp";

const MARKET = "Good for you. Better for the planet.";
const ADMIN = "A growing circular economy.";

describe("who ends up where", () => {
  test("signed-out visitors are sent to sign in", () => {
    renderAt("/admin", { status: "signedOut" });
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: ADMIN })).not.toBeInTheDocument();
  });

  test("a new account must choose a role", () => {
    renderAt("/farmer", { status: "needsRegistration", email: "a@b.pk", name: "A B" });
    expect(screen.getByRole("heading", { name: "How will you use it?" })).toBeInTheDocument();
  });

  test("a pending transporter only sees the waiting page", () => {
    const user = me("transporter", { status: "pending" });
    renderAt("/transporter", { status: "pending", user });
    expect(screen.getByRole("heading", { name: "Waiting for approval" })).toBeInTheDocument();
  });

  test("a suspended account is told so", () => {
    const user = me("buyer", { status: "suspended" });
    renderAt("/farmer", { status: "suspended", user });
    expect(screen.getByRole("heading", { name: "This account is suspended" })).toBeInTheDocument();
  });

  test("a buyer cannot open the admin page", () => {
    renderAt("/admin", signedIn("buyer"));
    expect(screen.queryByRole("heading", { name: ADMIN })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: MARKET })).toBeInTheDocument();
  });

  test("a signed-out visitor may open the marketplace", () => {
    renderAt("/market", { status: "signedOut" });
    expect(screen.getByRole("heading", { name: MARKET })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main navigation" })).not.toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Marketplace" })).toBeInTheDocument();
  });

  test("a farmer may browse the marketplace", () => {
    renderAt("/market", signedIn("farmer"));
    expect(screen.getByRole("heading", { name: MARKET })).toBeInTheDocument();
  });

  test("signed-in people skip the login page", () => {
    renderAt("/login", signedIn("buyer"));
    expect(screen.getByRole("heading", { name: MARKET })).toBeInTheDocument();
  });
});

describe("navigation", () => {
  const links = () =>
    within(screen.getByRole("navigation", { name: "Main navigation" }))
      .getAllByRole("link")
      .map((a) => a.textContent);

  test("a buyer sees only the marketplace and their details", () => {
    renderAt("/market", signedIn("buyer"));
    expect(links()).toEqual(["Marketplace", "My details"]);
  });

  test("a transporter sees their dashboard, the public marketplace and their details", () => {
    renderAt("/transporter", signedIn("transporter"));
    expect(links()).toEqual(["Transporter Dashboard", "Marketplace", "My details"]);
  });

  test("a factory sees its dashboard and the marketplace", () => {
    renderAt("/factory", signedIn("factory"));
    expect(links()).toEqual(["Factory Dashboard", "Marketplace", "My details"]);
  });

  test("an admin sees everything", async () => {
    renderAt("/admin", signedIn("admin"));
    await screen.findByRole("heading", { name: ADMIN });
    expect(links()).toHaveLength(7); // every page plus My details
  });

  test("there is no demo role switcher any more", async () => {
    renderAt("/admin", signedIn("admin"));
    await screen.findByRole("heading", { name: ADMIN });
    expect(screen.queryByLabelText("Demo Role Switcher")).not.toBeInTheDocument();
  });

  test("the header shows who is signed in and signing out returns to login", () => {
    renderAt("/farmer", signedIn("farmer"));
    expect(screen.getByText("Test User")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
