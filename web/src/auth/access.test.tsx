import { fireEvent, screen, within } from "@testing-library/react";
import { me, renderAt, signedIn } from "@/test/renderApp";

const MARKET = "Good for you. Better for the planet.";
const FARMER = "Assalam-o-Alaikum, Aslam!";
const ADMIN = "A growing circular economy.";

describe("who ends up where", () => {
  test("signed-out visitors are sent to sign in", () => {
    renderAt("/admin", { status: "signedOut" });
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: ADMIN })).not.toBeInTheDocument();
  });

  test("a new account must choose a role", () => {
    renderAt("/market", { status: "needsRegistration", email: "a@b.pk", name: "A B" });
    expect(screen.getByRole("heading", { name: "How will you use it?" })).toBeInTheDocument();
  });

  test("a pending transporter only sees the waiting page", () => {
    const user = me("transporter", { status: "pending" });
    renderAt("/transporter", { status: "pending", user });
    expect(screen.getByRole("heading", { name: "Waiting for approval" })).toBeInTheDocument();
  });

  test("a suspended account is told so", () => {
    const user = me("buyer", { status: "suspended" });
    renderAt("/market", { status: "suspended", user });
    expect(screen.getByRole("heading", { name: "This account is suspended" })).toBeInTheDocument();
  });

  test("a buyer cannot open the admin page", () => {
    renderAt("/admin", signedIn("buyer"));
    expect(screen.queryByRole("heading", { name: ADMIN })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: MARKET })).toBeInTheDocument();
  });

  test("a farmer cannot open the marketplace", () => {
    renderAt("/market", signedIn("farmer"));
    expect(screen.queryByRole("heading", { name: MARKET })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: FARMER })).toBeInTheDocument();
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

  test("a buyer sees only the marketplace", () => {
    renderAt("/market", signedIn("buyer"));
    expect(links()).toEqual(["Marketplace"]);
  });

  test("a transporter sees only their dashboard", () => {
    renderAt("/transporter", signedIn("transporter"));
    expect(links()).toEqual(["Transporter Dashboard"]);
  });

  test("a factory sees its dashboard and the marketplace", () => {
    renderAt("/factory", signedIn("factory"));
    expect(links()).toEqual(["Factory Dashboard", "Marketplace"]);
  });

  test("an admin sees everything", async () => {
    renderAt("/admin", signedIn("admin"));
    await screen.findByRole("heading", { name: ADMIN });
    expect(links()).toHaveLength(6);
  });

  test("there is no demo role switcher any more", async () => {
    renderAt("/admin", signedIn("admin"));
    await screen.findByRole("heading", { name: ADMIN });
    expect(screen.queryByLabelText("Demo Role Switcher")).not.toBeInTheDocument();
  });

  test("the header shows who is signed in and signing out returns to login", () => {
    renderAt("/market", signedIn("buyer"));
    expect(screen.getByText("Test User")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
