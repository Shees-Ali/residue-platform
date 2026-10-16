import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LIMITS } from "@/lib/validation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Leaf, Minus, PackageCheck, Plus, Search, ShoppingBag, Sprout, Trash2 } from "lucide-react";
import { api } from "@/api/client";
import { ORDERS_KEY, PRODUCTS_KEY, useOrders, useProducts } from "@/api/hooks";
import { unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { SplitBreakdown, pkr } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/auth/AuthProvider";
import field from "@/assets/punjab-field.jpg";
import { PRODUCT_CATEGORIES, categoryImage, validateQuantity } from "@/lib/products";
import { QueryBoundary, SectionHead, when } from "./common";

type Product = components["schemas"]["ProductOut"];
type Order = components["schemas"]["OrderOut"];

const CART_KEY = "residue-cart-v2";
const ALL = "All products";

function useCart() {
  const [cart, setCart] = useState<Record<string, number>>(() => {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY) ?? "{}") as Record<string, number>;
    } catch {
      return {}; // private mode or a bad value: start with an empty cart
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(CART_KEY, JSON.stringify(cart));
    } catch {
      /* storage is a convenience, the cart still works without it */
    }
  }, [cart]);
  const change = (id: string, delta: number) =>
    setCart((c) => {
      const next = Math.max(0, (c[id] ?? 0) + delta);
      const { [id]: _gone, ...rest } = c;
      return next === 0 ? rest : { ...rest, [id]: next };
    });
  const remove = (ids: string[]) => setCart((c) => Object.fromEntries(Object.entries(c).filter(([id]) => !ids.includes(id))));
  return { cart, change, remove };
}

interface LineResult {
  product: Product;
  quantity: number;
  order?: Order;
  error?: string;
}

/** The marketplace: real products, a cart, and a checkout that shows the four-way split. */
export function Marketplace() {
  const { user } = useAuth();
  const products = useProducts();
  const { cart, change, remove } = useCart();
  const [category, setCategory] = useState(ALL);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Product | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [paying, setPaying] = useState(false);
  const [results, setResults] = useState<LineResult[] | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const isBuyer = user?.role === "buyer";

  const shelf = products.data ?? [];
  const visible = useMemo(
    () =>
      shelf.filter(
        (p) =>
          p.active &&
          (category === ALL || p.category === category) &&
          p.name.toLowerCase().includes(search.trim().toLowerCase()),
      ),
    [shelf, category, search],
  );
  const lines = shelf.filter((p) => (cart[p.id] ?? 0) > 0);
  const count = Object.values(cart).reduce((n, q) => n + q, 0);
  const total = lines.reduce((n, p) => n + p.unit_price * (cart[p.id] ?? 0), 0);
  const problems = lines.map((p) => ({ p, msg: validateQuantity(cart[p.id] ?? 0, p.stock) })).filter((x) => x.msg);

  function add(p: Product) {
    if ((cart[p.id] ?? 0) + 1 > p.stock) {
      toast.error(p.stock === 0 ? `${p.name} is out of stock` : `Only ${p.stock} of ${p.name} left in stock`);
      return;
    }
    change(p.id, 1);
    toast.info(`${p.name} added to your cart`);
  }

  /** One order per cart line, one after the other, so each line has its own result. */
  async function checkout() {
    if (problems.length) {
      toast.error(problems.map((x) => `${x.p.name}: ${x.msg}`).join("; "));
      return;
    }
    setPaying(true);
    const done: LineResult[] = [];
    for (const product of lines) {
      const quantity = cart[product.id] ?? 0;
      try {
        const order = await unwrap(api.POST("/api/orders", { body: { product_id: product.id, quantity } }));
        done.push({ product, quantity, order });
      } catch (e) {
        done.push({ product, quantity, error: e instanceof Error ? e.message : "Could not place this order." });
      }
    }
    setPaying(false);
    remove(done.filter((r) => r.order).map((r) => r.product.id));
    for (const key of [PRODUCTS_KEY, ORDERS_KEY]) void qc.invalidateQueries({ queryKey: key });
    setCartOpen(false);
    setResults(done);
  }

  return (
    <>
      <div className="market-top">
        <div>
          <div className="eyebrow">THE RESIDUE PLATFORM MARKETPLACE</div>
          <h1>Good for you. Better for the planet.</h1>
        </div>
        <div className="flex items-center gap-2">
          {!user && (
            <Button asChild variant="outline" className="h-11">
              <Link to="/login">Sign in</Link>
            </Button>
          )}
          <Button variant="outline" onClick={() => setCartOpen(true)} className="h-11">
            <ShoppingBag />
            My cart <span className="cart-count">{count}</span>
          </Button>
        </div>
      </div>
      <div className="market-hero">
        <img src={field} width={1600} height={800} alt="Harvested rice straw in Punjab, the source of the products" />
        <div className="banner-shade" />
        <div className="banner-copy">
          <span className="banner-eyebrow">
            <Leaf size={15} />
            MADE FROM HARVEST. MADE FOR TOMORROW.
          </span>
          <h2>
            Harvested in Punjab.
            <br />
            Reimagined for everyday.
          </h2>
          <p>Thoughtfully made products. Rooted in a circular future.</p>
        </div>
      </div>
      <div className="market-promises">
        <span><Leaf />Made from crop residue</span>
        <span><Sprout />Supporting Punjab farmers</span>
        <span><PackageCheck />Less waste. More value.</span>
      </div>

      <div id="market-products" className="market-filters">
        <div className="category-tabs">
          {[ALL, ...PRODUCT_CATEGORIES].map((c) => (
            <Button key={c} variant="ghost" className={category === c ? "category-active" : ""} onClick={() => setCategory(c)}>
              {c}
            </Button>
          ))}
        </div>
        <label className="search-field">
          <Search size={17} />
          <input maxLength={LIMITS.search.max} placeholder="Search products" aria-label="Search products" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>

      <QueryBoundary q={products} what="the products">
        {() => (
          <>
            <div className="mb-5 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">{visible.length} thoughtfully made products</p>
            </div>
            <div className="product-grid">
              {visible.map((p) => (
                <article className="product-card" key={p.id}>
                  <Button variant="ghost" className="product-image-button" onClick={() => setSelected(p)} aria-label={`View ${p.name}`}>
                    <img src={categoryImage(p.category)} width={512} height={512} loading="lazy" alt={p.name} />
                    <span className="product-tag"><Leaf size={12} />Circular choice</span>
                  </Button>
                  <div className="product-copy">
                    <span className="eyebrow">{p.category}</span>
                    <Button variant="link" className="product-title" onClick={() => setSelected(p)}>{p.name}</Button>
                    <p>{p.description}</p>
                    <div className="product-bottom">
                      <div>
                        <strong>{pkr(p.unit_price)}</strong>
                        <small>{p.unit} · {p.stock > 0 ? `${p.stock} left` : "out of stock"}</small>
                      </div>
                      <Button variant="outline" size="icon" title={`Add ${p.name} to cart`} aria-label={`Add ${p.name} to cart`} disabled={p.stock === 0} onClick={() => add(p)}>
                        <Plus />
                      </Button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
            {!visible.length && <div className="empty-state">No products match your search.</div>}
          </>
        )}
      </QueryBoundary>

      {isBuyer && <MyOrders />}

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="product-dialog">
          {selected && (
            <>
              <img src={categoryImage(selected.category)} alt={selected.name} width={512} height={512} />
              <span className="eyebrow">{selected.category}</span>
              <DialogTitle>{selected.name}</DialogTitle>
              <DialogDescription>{selected.description || "Made from agricultural residue in Punjab."}</DialogDescription>
              <div className="flex items-center justify-between">
                <div>
                  <strong className="text-xl">{pkr(selected.unit_price)}</strong>
                  <p className="text-sm text-muted-foreground">{selected.unit} · sold by {selected.factory_name}</p>
                </div>
                <Button disabled={selected.stock === 0} onClick={() => { add(selected); setSelected(null); }}>
                  <ShoppingBag />
                  Add to cart
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Sheet open={cartOpen} onOpenChange={setCartOpen}>
        <SheetContent className="cart-sheet">
          <SheetTitle>Your circular choices <span className="text-muted-foreground">({count})</span></SheetTitle>
          <SheetDescription>Payment is simulated. Each item becomes one order.</SheetDescription>
          <div className="cart-items">
            {lines.map((p) => {
              const msg = validateQuantity(cart[p.id] ?? 0, p.stock);
              return (
                <div className="cart-item" key={p.id}>
                  <img src={categoryImage(p.category)} alt={p.name} width={80} height={80} />
                  <div className="min-w-0 flex-1">
                    <h3>{p.name}</h3>
                    <p>{pkr(p.unit_price)} · {p.unit}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <Button variant="outline" size="icon" aria-label={`Decrease ${p.name}`} onClick={() => change(p.id, -1)}><Minus /></Button>
                      <span className="w-5 text-center text-sm">{cart[p.id]}</span>
                      <Button variant="outline" size="icon" aria-label={`Increase ${p.name}`} disabled={(cart[p.id] ?? 0) >= p.stock} onClick={() => change(p.id, 1)}><Plus /></Button>
                      <Button variant="ghost" size="icon" aria-label={`Remove ${p.name}`} onClick={() => change(p.id, -(cart[p.id] ?? 0))}><Trash2 /></Button>
                    </div>
                    {msg && <p className="field-error mt-1">{msg}</p>}
                  </div>
                </div>
              );
            })}
          </div>
          {!lines.length && (
            <div className="empty-state">
              <ShoppingBag size={32} />
              <h3>Your cart is waiting for a greener choice.</h3>
              <Button onClick={() => setCartOpen(false)}>Explore products</Button>
            </div>
          )}
          {lines.length > 0 && (
            <div className="cart-summary">
              <div className="flex justify-between text-lg font-semibold"><span>Subtotal</span><span>{pkr(total)}</span></div>
              {isBuyer ? (
                <Button className="mt-4 w-full" loading={paying} onClick={() => void checkout()}>
                  Place order <ArrowRight />
                </Button>
              ) : user ? (
                <p className="auth-note my-4">Only buyers can place orders. Sign in with a buyer account to check out.</p>
              ) : (
                <Button asChild className="mt-4 w-full">
                  <Link to="/login">Sign in to buy <ArrowRight /></Link>
                </Button>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={!!results} onOpenChange={(open) => !open && setResults(null)}>
        <DialogContent className="form-dialog">
          <DialogTitle>Your order</DialogTitle>
          <DialogDescription>
            {results?.filter((r) => r.order).length ?? 0} of {results?.length ?? 0} items were ordered.
          </DialogDescription>
          <div className="auth-stack">
            {results?.map((r) => (
              <div key={r.product.id} className="job-card">
                <h3>{r.quantity} × {r.product.name}</h3>
                {r.order ? (
                  <>
                    <p className="text-sm">Paid {pkr(r.order.total)}. Here is how the sale is shared:</p>
                    <SplitBreakdown totalCents={r.order.total} splitCents={Object.fromEntries(r.order.splits.map((s) => [s.party, s.amount]))} />
                  </>
                ) : (
                  <p className="field-error">Not ordered: {r.error}. It is still in your cart.</p>
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-end"><Button onClick={() => setResults(null)}>Done</Button></div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** A buyer's past orders and how each sale was split. */
function MyOrders() {
  const orders = useOrders();
  return (
    <section aria-label="My orders" className="mt-10">
      <SectionHead title="My orders" />
      <QueryBoundary q={orders} what="your orders">
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">No orders yet.</div>
          ) : (
            <div className="jobs-grid">
              {rows.map((o) => (
                <article className="job-card" key={o.id}>
                  <h3>{o.quantity} × {o.product_name ?? "Product"}</h3>
                  <p className="table-sub">{when(o.created_at)} · {o.status}</p>
                  <p className="text-sm">Total <strong>{pkr(o.total)}</strong></p>
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

