import { fireEvent, screen, waitFor } from "@testing-library/react";
import { api } from "@/api/client";
import { me, renderAt } from "@/test/renderApp";

const start = () =>
  renderAt("/signup", { status: "needsRegistration", email: "a@b.pk", name: "Asma" });
const pick = (name: RegExp) => fireEvent.click(screen.getByRole("radio", { name }));

test("the name is prefilled and every self-signup role is offered, never admin", () => {
  start();
  expect(screen.getByLabelText("Your name")).toHaveValue("Asma");
  const names = screen
    .getAllByRole("radio")
    .map((r) => r.querySelector("strong")?.textContent);
  expect(names).toEqual(["Farmer", "Transporter", "Factory", "Buyer"]);
});

test("a buyer finishes straight away with just a name", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({
    data: me("buyer", { display_name: "Asma" }),
    response: { status: 201 },
  } as never);
  start();
  pick(/Buyer/);
  expect(screen.getByRole("button", { name: "Finish" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  await waitFor(() =>
    expect(api.POST).toHaveBeenCalledWith("/api/me/register", {
      body: { role: "buyer", display_name: "Asma" },
    }),
  );
});

test("a transporter is told an admin approves them and must give phone and place", () => {
  start();
  pick(/Transporter/);
  expect(screen.getByRole("button", { name: "Submit for approval" })).toBeInTheDocument();
  expect(screen.getByLabelText(/Phone/)).toBeInTheDocument();
  expect(screen.getByLabelText("Village or area")).toBeInTheDocument();
});

test("a factory chooses residues and the price is sent in paisa", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({
    data: me("factory", { status: "pending" }),
    response: { status: 201 },
  } as never);
  start();
  pick(/Factory/);
  fireEvent.change(screen.getByLabelText("Factory name"), { target: { value: "Green Mill" } });
  fireEvent.change(screen.getByLabelText(/Price you pay/), { target: { value: "4000" } });
  fireEvent.change(screen.getByLabelText("Village or area"), { target: { value: "Raiwind" } });
  fireEvent.click(screen.getByLabelText("Rice straw"));
  fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
  await waitFor(() => expect(api.POST).toHaveBeenCalled());
  expect(api.POST).toHaveBeenCalledWith("/api/me/register", {
    body: {
      role: "factory",
      display_name: "Asma",
      district: "Lahore",
      village: "Raiwind",
      factory: { name: "Green Mill", price_per_tonne: 400000, residues: ["rice_straw"] },
    },
  });
});

test("a factory cannot submit without a residue", async () => {
  start();
  pick(/Factory/);
  fireEvent.change(screen.getByLabelText("Factory name"), { target: { value: "Green Mill" } });
  fireEvent.change(screen.getByLabelText(/Price you pay/), { target: { value: "4000" } });
  fireEvent.change(screen.getByLabelText("Village or area"), { target: { value: "Raiwind" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose at least one residue");
});

test("a farmer can finish with no phone at all", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({
    data: me("farmer", { display_name: "Asma" }),
    response: { status: 201 },
  } as never);
  start();
  expect(screen.getByLabelText("Phone (optional)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  await waitFor(() =>
    expect(api.POST).toHaveBeenCalledWith("/api/me/register", {
      body: { role: "farmer", display_name: "Asma" },
    }),
  );
});

test("a farmer's phone is sent when given", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({ data: me("farmer"), response: { status: 201 } } as never);
  start();
  fireEvent.change(screen.getByLabelText("Phone (optional)"), { target: { value: "0313 1087151" } });
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  await waitFor(() =>
    expect(api.POST).toHaveBeenCalledWith("/api/me/register", {
      body: { role: "farmer", display_name: "Asma", phone: "+923131087151" },
    }),
  );
});

test("a phone that was typed must still be a real mobile number", async () => {
  start();
  fireEvent.change(screen.getByLabelText("Phone (optional)"), { target: { value: "0350 12" } });
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  expect(await screen.findAllByText(/not a valid Pakistan mobile number/)).not.toHaveLength(0);
  expect(api.POST).not.toHaveBeenCalled();
});

test("every text input stops at its limit", () => {
  start();
  expect(screen.getByLabelText("Your name")).toHaveAttribute("maxLength", "80");
  expect(screen.getByLabelText("Phone (optional)")).toHaveAttribute("maxLength", "22");
});

test("a refusal from the API is shown to the person", async () => {
  vi.mocked(api.POST).mockResolvedValueOnce({
    error: { detail: "That email is already registered" },
    response: { status: 409 },
  } as never);
  start();
  pick(/Buyer/);
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That email is already registered");
});
