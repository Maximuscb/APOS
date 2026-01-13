// frontend/src/App.tsx
import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPut } from "./lib/api";
import { AdjustInventoryForm } from "./components/AdjustInventoryForm";
import { CreateProductForm } from "./components/CreateProductForm";
import { InventoryLedger } from "./components/InventoryLedger";
import { MasterLedger } from "./components/MasterLedger";
import { ProductsTable } from "./components/ProductsTable";
import { ReceiveInventoryForm } from "./components/ReceiveInventoryForm";

type Health = any;

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
  store_id: number;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [invRefreshToken, setInvRefreshToken] = useState(0);
  const [asOf, setAsOf] = useState<string>(""); // "" or ISO-like string

  async function load() {
    setErr(null);
    setLoadingProducts(true);
    try {
      const h = await apiGet<Health>("/health");
      setHealth(h);

      const p = await apiGet<{ items: Product[]; count: number }>("/api/products");
      setProducts(p.items);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load");
    } finally {
      setLoadingProducts(false);
    }
  }

  async function deleteProduct(id: number) {
    setErr(null);
    try {
      await apiDelete(`/api/products/${id}`);
      await load();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to delete product");
    }
  }

  async function updateProduct(
    id: number,
    patch: { name: string; price_cents: number | null; is_active: boolean }
  ) {
    setErr(null);
    try {
      await apiPut(`/api/products/${id}`, patch);
      await load();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to update product");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      style={{
        padding: 24,
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>APOS</h1>
        <button onClick={load} style={{ padding: "8px 12px", cursor: "pointer" }}>
          Refresh
        </button>
      </div>

      <div style={{ marginTop: 8, color: "#444" }}>
        Backend:{" "}
        {health ? (
          <span style={{ fontFamily: "monospace" }}>{JSON.stringify(health)}</span>
        ) : (
          <span>…</span>
        )}
      </div>

      {err && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            border: "1px solid #f3b4b4",
            background: "#fff5f5",
            color: "#9b1c1c",
          }}
        >
          {err}
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <h2 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600 }}>Products</h2>

        <div style={{ display: "flex", gap: 8, alignItems: "end", marginBottom: 8 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "#444" }}>As of (optional)</label>
            <input
              type="datetime-local"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              style={{ padding: 6 }}
            />
          </div>
          <button
            onClick={() => setInvRefreshToken((n) => n + 1)}
            style={{ padding: "8px 12px", cursor: "pointer" }}
          >
            Apply
          </button>
        </div>

        {loadingProducts ? (
          <div>Loading…</div>
        ) : (
          <>
            <CreateProductForm onCreated={load} />
            <ReceiveInventoryForm
              products={products}
              onReceived={async () => {
                await load();
                setInvRefreshToken((n) => n + 1);
              }}
            />
            <AdjustInventoryForm
              products={products}
              onAdjusted={async () => {
                await load();
                setInvRefreshToken((n) => n + 1);
              }}
            />

            <InventoryLedger products={products} refreshToken={invRefreshToken} asOf={asOf} />

            <MasterLedger storeId={1} refreshToken={invRefreshToken} asOf={asOf} />

            <div style={{ marginTop: 12 }}>
              <ProductsTable
                products={products}
                onDelete={deleteProduct}
                onUpdate={updateProduct}
                asOf={asOf}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
