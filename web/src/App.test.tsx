import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

const cases: [string, string][] = [
  ["/admin", "Admin dashboard"],
  ["/transporter", "Transporter board"],
  ["/factory", "Factory dashboard"],
  ["/market", "Marketplace"],
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

test("health page", () => {
  render(
    <MemoryRouter initialEntries={["/health"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("health")).toHaveTextContent("ok");
});
