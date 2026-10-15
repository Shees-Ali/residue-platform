import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { api } from "@/api/client";
import { fail, mockGet, ok, posted } from "@/test/mockApi";
import { renderAt, signedIn } from "@/test/renderApp";

const product = (over: Record<string, unknown> = {}) => ({
  id: "p1", factory_id: "f1", factory_name: "Green Mill", name: "Biomass pellets", unit_price: 2_500_000,
  stock: 10, category: "Clean Energy", unit: "per 25 kg bag", description: "Dense pellets for boilers.",
  active: true, ...over,
});
const compost = product({ id: "p2", name: "Compost", category: "Farming & Garden", unit_price: 1_200_000, stock: 1 });
const order = (over: Record<string, unknown> = {}) => ({
  id: "o1", product_id: "p1", product_name: "Biomass pellets", quantity: 2, total: 5_000_000, status: "paid",
  created_at: "2026-10-16T08:00:00Z", shares_total_bps: 10_000, amounts_total: 5_000_000,
  splits: [
    { party: "farmer", share_bps: 5000, amount: 2_500_000 },
    { party: "factory", share_bps: 3000, amount: 1_500_000 },
    { party: "ngo", share_bps: 500, amount: 250_000 },
    { party: "platform", share_bps: 1500, amount: 750_000 },
  ],
  ...over,
});

beforeEach(() => localStorage.clear());

describe("marketplace", () => {
  const shop = (role: "buyer" | "factory" | "admin" = "buyer") => {
    mockGet({ "/api/products": [product(), compost, product({ id: "p3", name: "Hidden", active: false })], "/api/orders": [] });
    renderAt("/market", signedIn(role));
  };

  test("shows what is for sale with real prices, units and stock", async () => {
    shop();
    expect(await screen.findByRole("button", { name: "View Biomass pellets" })).toBeInTheDocument();
    expect(screen.getByText("PKR 25,000")).toBeInTheDocument();
    expect(screen.getByText(/per 25 kg bag · 10 left/)).toBeInTheDocument();
    expect(screen.queryByText("Hidden")).not.toBeInTheDocument(); // unlisted
    expect(screen.getByText("2 thoughtfully made products")).toBeInTheDocument();
  });

  test("categories and search narrow the shelf", async () => {
    shop();
    await screen.findByRole("button", { name: "View Biomass pellets" });
    fireEvent.click(screen.getByRole("button", { name: "Farming & Garden" }));
    expect(screen.queryByRole("button", { name: "View Biomass pellets" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Compost" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "All products" }));
    fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "zzz" } });
    expect(screen.getByText("No products match your search.")).toBeInTheDocument();
  });

  test("the cart cannot hold more than the stock", async () => {
    shop();
    fireEvent.click(await screen.findByRole("button", { name: "Add Compost to cart" })); // only 1 in stock
    fireEvent.click(screen.getByRole("button", { name: "Add Compost to cart" }));
    expect(await screen.findByText("Only 1 of Compost left in stock")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /My cart/ }));
    const cart = await screen.findByRole("dialog");
    expect(within(cart).getByRole("button", { name: "Increase Compost" })).toBeDisabled();
  });

  test("a buyer checks out: one order per line and the split is shown", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(order()));
    shop();
    fireEvent.click(await screen.findByRole("button", { name: "Add Biomass pellets to cart" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Biomass pellets to cart" }));
    fireEvent.click(screen.getByRole("button", { name: /My cart/ }));
    const cart = await screen.findByRole("dialog");
    expect(within(cart).getByText("PKR 50,000")).toBeInTheDocument();
    fireEvent.click(within(cart).getByRole("button", { name: /Place order/ }));
    await waitFor(() => expect(posted("/api/orders")).toHaveLength(1));
    expect(posted("/api/orders")[0][1].body).toEqual({ product_id: "p1", quantity: 2 });
    const done = await screen.findByText("1 of 1 items were ordered.");
    expect(done).toBeInTheDocument();
    expect(screen.getByText(/Paid PKR 50,000/)).toBeInTheDocument();
    expect(screen.getByText(/farmer · PKR 25,000/)).toBeInTheDocument();
    expect(screen.getByText(/platform · PKR 7,500/)).toBeInTheDocument();
    expect(localStorage.getItem("residue-cart-v2")).toBe("{}"); // bought items leave the cart
  });

  test("a line that fails stays in the cart with its reason; the others go through", async () => {
    vi.mocked(api.POST)
      .mockResolvedValueOnce(ok(order()))
      .mockResolvedValueOnce(fail("Not enough stock, or the product is not for sale", 409));
    shop();
    fireEvent.click(await screen.findByRole("button", { name: "Add Biomass pellets to cart" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Compost to cart" }));
    fireEvent.click(screen.getByRole("button", { name: /My cart/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /Place order/ }));
    expect(await screen.findByText("1 of 2 items were ordered.")).toBeInTheDocument();
    expect(screen.getByText(/Not ordered: Not enough stock/)).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("residue-cart-v2")!)).toEqual({ p2: 1 });
  });

  test("checkout spins while the orders go through", async () => {
    let finish!: (v: unknown) => void;
    vi.mocked(api.POST).mockReturnValueOnce(new Promise((r) => (finish = r)) as never);
    shop();
    fireEvent.click(await screen.findByRole("button", { name: "Add Biomass pellets to cart" }));
    fireEvent.click(screen.getByRole("button", { name: /My cart/ }));
    const cart = await screen.findByRole("dialog");
    fireEvent.click(within(cart).getByRole("button", { name: /Place order/ }));
    await waitFor(() => expect(within(cart).getByRole("button", { name: /Place order/ })).toHaveAttribute("aria-busy", "true"));
    finish(ok(order()));
    expect(await screen.findByText("1 of 1 items were ordered.")).toBeInTheDocument();
  });

  test("only buyers can place orders", async () => {
    shop("admin");
    fireEvent.click(await screen.findByRole("button", { name: "Add Biomass pellets to cart" }));
    fireEvent.click(screen.getByRole("button", { name: /My cart/ }));
    const cart = await screen.findByRole("dialog");
    expect(within(cart).getByText(/Only buyers can place orders/)).toBeInTheDocument();
    expect(within(cart).queryByRole("button", { name: /Place order/ })).not.toBeInTheDocument();
  });

  test("a buyer sees past orders with their split", async () => {
    mockGet({ "/api/products": [product()], "/api/orders": [order()] });
    renderAt("/market", signedIn("buyer"));
    const section = await screen.findByRole("region", { name: "My orders" });
    expect(await within(section).findByText("2 × Biomass pellets")).toBeInTheDocument();
    expect(within(section).getByText(/ngo · PKR 2,500/)).toBeInTheDocument();
  });

  test("a failed shelf offers a retry", async () => {
    mockGet({ "/api/products": fail("down", 403) });
    renderAt("/market", signedIn("buyer"));
    expect(await screen.findByRole("button", { name: "Try again" }, { timeout: 4000 })).toBeInTheDocument();
  });
});

describe("factory: products and orders", () => {
  const start = (rows = [product(), product({ id: "p4", name: "Old stock", active: false, stock: 0 })]) => {
    mockGet({ "/api/jobs": [], "/api/products": rows, "/api/orders": [order()] });
    renderAt("/factory", signedIn("factory"));
  };

  test("lists its products including unlisted ones, and the orders with their split", async () => {
    start();
    const shelf = await screen.findByRole("region", { name: "My products" });
    expect(await within(shelf).findByText("Old stock")).toBeInTheDocument();
    expect(within(shelf).getByText("Unlisted")).toBeInTheDocument();
    const orders = screen.getByRole("region", { name: "Orders" });
    expect(await within(orders).findByText("2 × Biomass pellets")).toBeInTheDocument();
    expect(within(orders).getByText(/factory · PKR 15,000/)).toBeInTheDocument();
  });

  test("listing a product checks every rule and shows each message under its field", async () => {
    start([]);
    fireEvent.click(await screen.findByRole("button", { name: /List a product/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Price (PKR)"), { target: { value: "2000000" } });
    fireEvent.change(within(dialog).getByLabelText("Stock"), { target: { value: "-4" } });
    fireEvent.change(within(dialog).getByLabelText("Sold as"), { target: { value: "x" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "List product" }));
    expect((await within(dialog).findAllByText("Product name must be at least 2 characters")).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("Price must be between PKR 1 and PKR 1,000,000").length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("Stock must be a whole number from 0 to 1,000,000").length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("Unit must be at least 2 characters").length).toBeGreaterThan(0);
    expect(within(dialog).getByLabelText("Product name")).toHaveFocus();
    expect(posted("/api/products")).toHaveLength(0);
  });

  test("a valid product is sent in paisa with its category, unit and description", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(ok(product({ name: "Wood boards", category: "Building Materials" })));
    start([]);
    fireEvent.click(await screen.findByRole("button", { name: /List a product/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Product name"), { target: { value: "Wood boards" } });
    fireEvent.change(within(dialog).getByLabelText("Category"), { target: { value: "Building Materials" } });
    fireEvent.change(within(dialog).getByLabelText("Price (PKR)"), { target: { value: "1500" } });
    fireEvent.change(within(dialog).getByLabelText("Stock"), { target: { value: "40" } });
    fireEvent.change(within(dialog).getByLabelText(/Description/), { target: { value: "Pressed boards." } });
    fireEvent.click(within(dialog).getByRole("button", { name: "List product" }));
    await waitFor(() => expect(posted("/api/products")).toHaveLength(1));
    expect(posted("/api/products")[0][1].body).toEqual({
      name: "Wood boards", unit_price: 150_000, stock: 40, category: "Building Materials",
      unit: "per 25 kg bag", description: "Pressed boards.",
    });
    expect(await screen.findByText("Wood boards is now for sale.")).toBeInTheDocument();
  });

  test("the API field errors land under the matching inputs", async () => {
    vi.mocked(api.POST).mockResolvedValueOnce(
      fail("Price must be between PKR 1 and PKR 1,000,000", 422, [
        { field: "unit_price", message: "Price must be between PKR 1 and PKR 1,000,000", code: "value_error" },
      ]),
    );
    start([]);
    fireEvent.click(await screen.findByRole("button", { name: /List a product/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Product name"), { target: { value: "Pellets" } });
    fireEvent.change(within(dialog).getByLabelText("Price (PKR)"), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Stock"), { target: { value: "5" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "List product" }));
    await waitFor(() => expect(within(dialog).getByLabelText("Price (PKR)")).toHaveAttribute("aria-invalid", "true"));
  });

  test("editing keeps the price in rupees and unlisting is one click", async () => {
    vi.mocked(api.PATCH).mockResolvedValue(ok(product({ active: false })));
    start([product()]);
    const shelf = await screen.findByRole("region", { name: "My products" });
    fireEvent.click(await within(shelf).findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Price (PKR)")).toHaveValue("25000");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    fireEvent.click(await within(shelf).findByRole("button", { name: "Unlist" }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalled());
    expect(vi.mocked(api.PATCH).mock.calls[0][1]).toMatchObject({ body: { active: false } });
  });

  test("an admin looking at the page cannot list products", async () => {
    mockGet({ "/api/jobs": [], "/api/products": [product()], "/api/orders": [] });
    renderAt("/factory", signedIn("admin"));
    const shelf = await screen.findByRole("region", { name: "My products" });
    expect(await within(shelf).findByText("Biomass pellets")).toBeInTheDocument();
    expect(within(shelf).queryByRole("button", { name: /List a product/ })).not.toBeInTheDocument();
  });
});
