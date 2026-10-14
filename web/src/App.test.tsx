import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

const cases: [string, string][] = [
  ["/farmer", "Assalam-o-Alaikum, Aslam!"],
  ["/transporter", "Move harvests forward."],
  ["/factory", "From residue to resources."],
  ["/market", "Good for you. Better for the planet."],
  ["/admin", "A growing circular economy."],
  ["/call", "Call widget (browser fallback)"],
];

test.each(cases)("route %s renders", (path, heading) => {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
});

test("root redirects to the marketplace", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: "Good for you. Better for the planet." })).toBeInTheDocument();
});

test("health page", () => {
  render(
    <MemoryRouter initialEntries={["/health"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("health")).toHaveTextContent("ok");
});
