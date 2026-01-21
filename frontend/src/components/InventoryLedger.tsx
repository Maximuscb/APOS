// Overview: React component for inventory ledger UI.

// frontend/src/components/InventoryLedger.tsx
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../lib/api";
import { datetimeLocalToUtcIso, utcIsoToLocalDisplay } from "../lib/time";

type InventoryTx = {
  id: number;
  store_id: number;
  product_id: number;
  type: string;
  quantity_delta: number;
  unit_cost_cents: number | null;
  note: string | null;
  occurred_at: string | null;
  created_at: string | null;
};

type Product = {
  id: number;
  sku: string;
  name: string;
  store_id: number;
};

function centsToDollars(cents: number | null): string {
  if (cents === null || cents === undefined) return "";
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const rem = abs % 100;
  return `${sign}$${dollars}.${rem.toString().padStart(2, "0")}`;
}

function hasTransactions(x: unknown): x is { transactions: InventoryTx[] } {
  return (
    typeof x === "object" &&
    x !== null &&
    "transactions" in x &&
    Array.isArray((x as { transactions?: unknown }).transactions)
  );
}

type Props = {
  products: Product[];
  refreshToken: number;
  asOf: string; // datetime-local from App.tsx ("" or "YYYY-MM-DDTHH:mm")
  storeId: number;
};

export function InventoryLedger({ products, refreshToken, asOf, storeId }: Props) {
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [rows, setRows] = useState<InventoryTx[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  // Keep selection stable; default to first product when list changes.
  useEffect(() => {
    if (products.length === 0) {
      setSelectedProductId(null);
      return;
    }
    setSelectedProductId((prev) => {
      if (prev && products.some((p) => p.id === prev)) return prev;
      return products[0].id;
    });
  }, [products]);

  // App.tsx supplies datetime-local; convert to UTC ISO for backend.
  const asOfUtcIso = useMemo(() => datetimeLocalToUtcIso(asOf), [asOf]);

  async function load() {
    if (!selectedProductId) {
      setRows([]);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();
      params.set("store_id", String(storeId));
      if (asOfUtcIso) params.set("as_of", asOfUtcIso);

      const suffix = `?${params.toString()}`;
      const data = await apiGet(`/api/inventory/${selectedProductId}/transactions${suffix}`);

      const txs: InventoryTx[] = Array.isArray(data) ? data : hasTransactions(data) ? data.transactions : [];
      setRows(txs);
    } catch (e: any) {
      setError(e?.message || "Failed to load inventory ledger.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProductId, asOfUtcIso, refreshToken, storeId]);

  if (products.length === 0) {
    return (
      <div className="form-card">
        <p className="helper-text" style={{ margin: 0 }}>No products yet.</p>
      </div>
    );
  }

  return (
    <div className="form-card">
      <div className="form-row" style={{ justifyContent: "space-between" }}>
        <div>
          <p className="form-title" style={{ margin: 0 }}>Inventory Ledger</p>
          <div className="helper-text">
            Store: {storeId}
            {asOfUtcIso ? (
              <>
                {" "}
                As-Of (UTC): <code>{asOfUtcIso}</code>
              </>
            ) : null}
          </div>
        </div>

        <div className="form-actions" style={{ alignItems: "flex-end" }}>
          <div className="form-stack">
            <label className="form-label">Product</label>
            <select
              value={selectedProductId ?? ""}
              onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : null)}
              className="select" style={{ width: 260 }}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} - {p.name}
                </option>
              ))}
            </select>
          </div>

          <button onClick={load} className="btn btn--ghost btn--sm" disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {error ? <div className="notice notice--error" style={{ marginBottom: 10 }}>{error}</div> : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Occurred (Local)</th>
            <th>Type</th>
            <th>Qty Delta</th>
            <th>Unit Cost</th>
            <th>Note</th>
            <th>Recorded (Local)</th>
            <th>Tx ID</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={7}>
                {loading ? "Loading..." : "No transactions found."}
              </td>
            </tr>
          ) : (
            rows.map((tx) => (
              <tr key={tx.id}>
                <td>{tx.occurred_at ? utcIsoToLocalDisplay(tx.occurred_at) : ""}</td>
                <td>{tx.type}</td>
                <td>{tx.quantity_delta}</td>
                <td>{centsToDollars(tx.unit_cost_cents)}</td>
                <td>{tx.note ?? ""}</td>
                <td>{tx.created_at ? utcIsoToLocalDisplay(tx.created_at) : ""}</td>
                <td>{tx.id}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
