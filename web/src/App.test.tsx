import { screen } from "@testing-library/react";
import { renderAt, signedIn } from "@/test/renderApp";
import type { Role } from "@/lib/auth";

const pages: [string, string][] = [
  ["/farmer", "Assalam-o-Alaikum, Aslam!"],
  ["/transporter", "Move harvests forward."],
  ["/factory", "From residue to resources."],
  ["/market", "Good for you. Better for the planet."],
  ["/admin", "A growing circular economy."],
  ["/call", "Call widget (browser fallback)"],
];

// An admin may open every page.
test.each(pages)("admin can open %s", async (path, heading) => {
  renderAt(path, signedIn("admin"));
  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
});

const homes: [Role, string][] = [
  ["farmer", "Assalam-o-Alaikum, Aslam!"],
  ["transporter", "Move harvests forward."],
  ["factory", "From residue to resources."],
  ["buyer", "Good for you. Better for the planet."],
  ["admin", "A growing circular economy."],
];

test.each(homes)("the root sends a %s to their own page", async (role, heading) => {
  renderAt("/", signedIn(role));
  expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
});

test("health page is public", () => {
  renderAt("/health", { status: "signedOut" });
  expect(screen.getByTestId("health")).toHaveTextContent("ok");
});
