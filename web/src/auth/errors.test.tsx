import { fireEvent, screen } from "@testing-library/react";
import { api } from "@/api/client";
import { renderAt } from "@/test/renderApp";
import { renderWithProviders } from "@/test/renderApp";
import { PageLoader } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";

test("a Google or Firebase sign-in error appears as a toast", async () => {
  // Firebase is mocked away in setupTests, so the sign-in call itself fails.
  renderAt("/login", { status: "signedOut" });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.pk" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret1" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});

test("a refusal when creating the account is toasted", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({
    error: { detail: "Already registered" },
    response: { status: 409 },
  } as never);
  renderAt("/signup", { status: "needsRegistration", email: "a@b.pk", name: "Asma" });
  fireEvent.click(screen.getByRole("radio", { name: /Buyer/ }));
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Already registered");
});

test("the page loader announces itself", () => {
  renderWithProviders(<PageLoader label="Loading your workspace…" />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading your workspace…");
});

test("a loading button is disabled and marked busy", () => {
  renderWithProviders(<Button loading>Save</Button>);
  const b = screen.getByRole("button", { name: "Save" });
  expect(b).toBeDisabled();
  expect(b).toHaveAttribute("aria-busy", "true");
});

