import { fireEvent, screen, waitFor } from "@testing-library/react";
import { api } from "@/api/client";
import { renderWithProviders as render } from "@/test/renderApp";
import { PendingApprovals } from "./approvals";

const transporter = {
  uid: "tr-1",
  email: "t@x.pk",
  role: "transporter",
  status: "pending",
  display_name: "Truck Co",
  phone: "+923001",
  created_at: "2026-10-15T00:00:00Z",
  details: { phone: "+923001", tier: 1, max_tonnes: 3 },
};
const factory = {
  ...transporter,
  uid: "f-1",
  role: "factory",
  display_name: "Green Mill",
  details: { name: "Green Mill", price_per_tonne: 400000, residues: ["rice_straw"] },
};

test("shows nothing when nobody is waiting", async () => {
  vi.mocked(api.GET).mockResolvedValueOnce({ data: [], response: { status: 200 } } as never);
  render(<PendingApprovals />);
  await waitFor(() =>
    expect(screen.queryByRole("region", { name: "Pending approvals" })).not.toBeInTheDocument(),
  );
});

test("lists pending accounts and approves a transporter at the chosen tier", async () => {
  vi.mocked(api.GET)
    .mockResolvedValueOnce({ data: [transporter, factory], response: { status: 200 } } as never)
    .mockResolvedValueOnce({ data: [factory], response: { status: 200 } } as never);
  vi.mocked(api.POST).mockResolvedValueOnce({ data: {}, response: { status: 200 } } as never);
  render(<PendingApprovals />);
  expect(await screen.findByText("Truck Co")).toBeInTheDocument();
  expect(screen.getByText(/Green Mill · PKR 4,000\/t · rice_straw/)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Tier for Truck Co"), { target: { value: "2" } });
  fireEvent.click(screen.getAllByRole("button", { name: /Approve/ })[0]);
  await waitFor(() =>
    expect(api.POST).toHaveBeenCalledWith("/api/users/{uid}/approve", {
      params: { path: { uid: "tr-1" } },
      body: { tier: 2 },
    }),
  );
  await waitFor(() => expect(screen.queryByText("Truck Co")).not.toBeInTheDocument());
});

test("a rejected request shows the reason", async () => {
  vi.mocked(api.GET).mockResolvedValue({ data: [factory], response: { status: 200 } } as never);
  vi.mocked(api.POST).mockResolvedValueOnce({
    error: { detail: "Cannot reject a user who is active" },
    response: { status: 409 },
  } as never);
  render(<PendingApprovals />);
  fireEvent.click(await screen.findByRole("button", { name: /Reject/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reject a user who is active");
});

test("shows a placeholder while loading, then the table", async () => {
  let release!: (v: unknown) => void;
  vi.mocked(api.GET).mockReturnValueOnce(new Promise((r) => (release = r)) as never);
  render(<PendingApprovals />);
  expect(screen.getByRole("region", { name: "Pending approvals" })).toHaveAttribute("aria-busy", "true");
  release({ data: [factory], response: { status: 200 } });
  expect(await screen.findByText("Green Mill")).toBeInTheDocument();
});

test("a failed load toasts the reason and offers a retry", async () => {
  vi.mocked(api.GET)
    .mockResolvedValueOnce({ error: { detail: "Forbidden" }, response: { status: 403 } } as never)
    .mockResolvedValueOnce({ data: [factory], response: { status: 200 } } as never);
  render(<PendingApprovals />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
  fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Green Mill")).toBeInTheDocument();
});
