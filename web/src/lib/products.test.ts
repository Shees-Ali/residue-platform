import { PRICE_HELP, PRODUCT_CATEGORIES, STOCK_HELP, categoryImage, validateProduct, validateQuantity } from "./products";

const good = { name: "Biomass pellets", price: "250", stock: "10", category: "Clean Energy", unit: "per 25 kg bag", description: "" };

describe("product rules", () => {
  test("a good product has no errors", () => {
    expect(validateProduct(good)).toEqual({});
    expect(validateProduct({ ...good, price: "1", stock: "0", description: "x".repeat(500) })).toEqual({});
  });

  test("every bad field is reported with the API field names", () => {
    const e = validateProduct({ name: "a", price: "", stock: "", category: "Weapons", unit: "x", description: "x".repeat(501) });
    expect(Object.keys(e).sort()).toEqual(["category", "description", "name", "stock", "unit", "unit_price"]);
    expect(e.name).toBe("Product name must be at least 2 characters");
    expect(e.unit_price).toBe("Price is required");
    expect(e.category).toBe("Category must be one of Clean Energy, Farming & Garden, Building Materials or Home & Living");
  });

  test.each(["0", "0.5", "1000001", "abc"])("a price of %s is outside PKR 1 to PKR 1,000,000", (price) => {
    expect(validateProduct({ ...good, price }).unit_price).toBe(PRICE_HELP);
  });

  test.each(["-1", "2.5", "1000001", "ten"])("a stock of %s is refused", (stock) => {
    expect(validateProduct({ ...good, stock }).stock).toBe(STOCK_HELP);
  });

  test("names and units have ceilings", () => {
    expect(validateProduct({ ...good, name: "x".repeat(121) }).name).toBe("Product name must be at most 120 characters");
    expect(validateProduct({ ...good, unit: "x".repeat(41) }).unit).toBe("Unit must be at most 40 characters");
  });
});

describe("cart quantity", () => {
  test("a whole number from 1 up to the stock", () => {
    expect(validateQuantity(2, 10)).toBeUndefined();
    expect(validateQuantity(0, 10)).toBe("Quantity must be a whole number between 1 and 1000");
    expect(validateQuantity(1.5, 10)).toBe("Quantity must be a whole number between 1 and 1000");
    expect(validateQuantity(11, 10)).toBe("Only 10 left in stock");
    expect(validateQuantity(1, 0)).toBe("Out of stock");
    expect(validateQuantity(1001, 5000)).toBe("Quantity must be a whole number between 1 and 1000");
  });
});

test("every category has a picture", () => {
  for (const c of PRODUCT_CATEGORIES) expect(categoryImage(c)).toBeTruthy();
  expect(categoryImage("Unknown")).toBeTruthy();
});
