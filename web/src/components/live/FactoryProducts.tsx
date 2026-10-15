import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/api/client";
import { ORDERS_KEY, PRODUCTS_KEY, useOrders, useProducts } from "@/api/hooks";
import { ApiError, unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { SplitBreakdown, pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { PRODUCT_CATEGORIES, validateProduct, type ProductValues } from "@/lib/products";
import { useFormErrors } from "@/lib/useFormErrors";
import { LIMITS, pkrToPaisa, summarize } from "@/lib/validation";
import { QueryBoundary, SectionHead, when } from "./common";

type Product = components["schemas"]["ProductOut"];

const BLANK: ProductValues = {
  name: "", price: "", stock: "", category: PRODUCT_CATEGORIES[0], unit: "per 25 kg bag", description: "",
};

/** The factory's shelf: list a product, change its price and stock, unlist it. */
export function FactoryProducts({ canAct }: { canAct: boolean }) {
  const products = useProducts();
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const toggle = useMutation({
    mutationFn: (p: Product) =>
      unwrap(api.PATCH("/api/products/{product_id}", { params: { path: { product_id: p.id } }, body: { active: !p.active } })),
    onSuccess: (p) => toast.info(p.active ? `${p.name} is for sale again.` : `${p.name} is unlisted.`),
    onSettled: () => void qc.invalidateQueries({ queryKey: PRODUCTS_KEY }),
  });
  return (
    <section aria-label="My products">
      <SectionHead title="My products">
        {canAct && (
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus />
            List a product
          </Button>
        )}
      </SectionHead>
      <QueryBoundary q={products} what="your products">
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">Nothing listed yet. List a product to sell it on the marketplace.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Category</th>
                    <th>Price</th>
                    <th>Stock</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id}>
                      <td className="font-medium">
                        {p.name}
                        <span className="table-sub">{p.unit}</span>
                      </td>
                      <td>{p.category}</td>
                      <td>{pkr(p.unit_price)}</td>
                      <td>{p.stock}</td>
                      <td>{p.active ? "For sale" : "Unlisted"}</td>
                      <td>
                        {canAct && (
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" onClick={() => setEditing(p)}>
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              loading={toggle.isPending && toggle.variables?.id === p.id}
                              disabled={toggle.isPending}
                              onClick={() => toggle.mutate(p)}
                            >
                              {p.active ? "Unlist" : "List"}
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </QueryBoundary>
      {editing && <ProductDialog product={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function ProductDialog({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const form = useFormErrors();
  const [v, setV] = useState<ProductValues>(
    product
      ? {
          name: product.name, price: String(product.unit_price / 100), stock: String(product.stock),
          category: product.category, unit: product.unit, description: product.description,
        }
      : BLANK,
  );
  const set = (key: keyof ProductValues, apiField: string) => (value: string) => {
    setV((old) => ({ ...old, [key]: value }));
    form.clear(apiField);
  };
  const save = useMutation({
    meta: { silent: true },
    mutationFn: () => {
      const body = {
        name: v.name.trim(),
        unit_price: pkrToPaisa(v.price) ?? 0,
        stock: Number(v.stock),
        category: v.category as (typeof PRODUCT_CATEGORIES)[number],
        unit: v.unit.trim(),
        description: v.description.trim(),
      };
      return product
        ? unwrap(api.PATCH("/api/products/{product_id}", { params: { path: { product_id: product.id } }, body }))
        : unwrap(api.POST("/api/products", { body }));
    },
    onSuccess: (p) => {
      toast.info(product ? `${p.name} updated.` : `${p.name} is now for sale.`);
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && Object.keys(e.fields).length) form.fail(e.fields);
      toast.error(e instanceof Error ? e.message : "Could not save the product.");
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: PRODUCTS_KEY }),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    const errors = validateProduct(v);
    if (Object.keys(errors).length) {
      form.fail(errors);
      toast.error(summarize(errors));
      return;
    }
    form.reset();
    save.mutate();
  }
  const err = form.errors;
  return (
    <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>{product ? "Edit product" : "List a product"}</DialogTitle>
        <DialogDescription>Buyers see this on the marketplace.</DialogDescription>
        <form noValidate ref={form.ref} onSubmit={submit} className="form-grid" aria-busy={save.isPending}>
          <fieldset disabled={save.isPending} className="bare-fieldset form-grid col-span-full">
            <Field label="Product name" error={err.name}>
              <input value={v.name} maxLength={120} onChange={(e) => set("name", "name")(e.target.value)} />
            </Field>
            <Field label="Category" error={err.category}>
              <select value={v.category} onChange={(e) => set("category", "category")(e.target.value)}>
                {PRODUCT_CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Price (PKR)" error={err.unit_price} hint="Between PKR 1 and PKR 1,000,000">
              <input inputMode="decimal" maxLength={LIMITS.moneyText.max} value={v.price} onChange={(e) => set("price", "unit_price")(e.target.value)} />
            </Field>
            <Field label="Stock" error={err.stock} hint="A whole number, up to 1,000,000">
              <input inputMode="numeric" maxLength={LIMITS.stockText.max} value={v.stock} onChange={(e) => set("stock", "stock")(e.target.value)} />
            </Field>
            <Field label="Sold as" error={err.unit} hint="For example: per 25 kg bag">
              <input value={v.unit} maxLength={40} onChange={(e) => set("unit", "unit")(e.target.value)} />
            </Field>
            <Field label="Description (optional)" error={err.description} hint="Up to 500 characters">
              <input value={v.description} maxLength={500} onChange={(e) => set("description", "description")(e.target.value)} />
            </Field>
            <div className="col-span-full flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={save.isPending}>
                {product ? "Save changes" : "List product"}
              </Button>
            </div>
          </fieldset>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Sales of the factory's products, each with the four-way split. */
export function FactoryOrders() {
  const orders = useOrders();
  return (
    <section aria-label="Orders" className="mt-8">
      <SectionHead title="Orders and revenue split" />
      <QueryBoundary q={orders} what="the orders">
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">No orders yet.</div>
          ) : (
            <div className="jobs-grid">
              {rows.map((o) => (
                <article className="job-card" key={o.id}>
                  <h3>{o.quantity} × {o.product_name ?? "Product"}</h3>
                  <p className="table-sub">{when(o.created_at)}</p>
                  <p className="text-sm">Order total <strong>{pkr(o.total)}</strong></p>
                  <SplitBreakdown totalCents={o.total} splitCents={Object.fromEntries(o.splits.map((s) => [s.party, s.amount]))} />
                </article>
              ))}
            </div>
          )
        }
      </QueryBoundary>
    </section>
  );
}
