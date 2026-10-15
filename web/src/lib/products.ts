import boards from "@/assets/boards.jpg";
import briquettes from "@/assets/briquettes.jpg";
import compost from "@/assets/compost.jpg";
import tableware from "@/assets/tableware.jpg";
import { pkrToPaisa, type Errors } from "./validation";

export const PRODUCT_CATEGORIES = ["Clean Energy", "Farming & Garden", "Building Materials", "Home & Living"] as const;
export type ProductCategory = (typeof PRODUCT_CATEGORIES)[number];

const IMAGES: Record<string, string> = {
  "Clean Energy": briquettes,
  "Farming & Garden": compost,
  "Building Materials": boards,
  "Home & Living": tableware,
};

/** Products have no upload; the picture follows the category. */
export const categoryImage = (category: string): string => IMAGES[category] ?? briquettes;

export const PRICE_HELP = "Price must be between PKR 1 and PKR 1,000,000";
export const STOCK_HELP = "Stock must be a whole number from 0 to 1,000,000";
export const QUANTITY_HELP = "Quantity must be a whole number between 1 and 1000";

export interface ProductValues {
  name: string;
  price: string; // PKR as typed
  stock: string;
  category: string;
  unit: string;
  description: string;
}

/** Errors for the product form, keyed by the API field names (the price is sent in paisa). */
export function validateProduct(v: ProductValues): Errors {
  const e: Errors = {};
  const name = v.name.trim();
  if (name.length < 2) e.name = "Product name must be at least 2 characters";
  else if (name.length > 120) e.name = "Product name must be at most 120 characters";
  const paisa = pkrToPaisa(v.price);
  if (!v.price.trim()) e.unit_price = "Price is required";
  else if (paisa === null || paisa < 100 || paisa > 100_000_000) e.unit_price = PRICE_HELP;
  if (!v.stock.trim()) e.stock = "Stock is required";
  else if (!/^\d+$/.test(v.stock.trim()) || Number(v.stock) > 1_000_000) e.stock = STOCK_HELP;
  if (!(PRODUCT_CATEGORIES as readonly string[]).includes(v.category)) {
    e.category = `Category must be one of ${PRODUCT_CATEGORIES.slice(0, -1).join(", ")} or ${PRODUCT_CATEGORIES.at(-1)}`;
  }
  const unit = v.unit.trim();
  if (unit.length < 2) e.unit = "Unit must be at least 2 characters";
  else if (unit.length > 40) e.unit = "Unit must be at most 40 characters";
  if (v.description.trim().length > 500) e.description = "Description must be at most 500 characters";
  return e;
}

/** A cart line must be a whole number from 1 up to the stock on the shelf (and at most 1000). */
export function validateQuantity(quantity: number, stock: number): string | undefined {
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 1000) return QUANTITY_HELP;
  if (quantity > stock) return stock === 0 ? "Out of stock" : `Only ${stock} left in stock`;
  return undefined;
}
