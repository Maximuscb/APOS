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

  const headerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 10,
  };

  const titleStyle: React.CSSProperties = {
    fontSize: 16,
    fontWeight: 600,
    margin: 0,
  };

  const labelStyle: React.CSSProperties = { fontSize: 12, color: "#444" };
  const tableStyle: React.CSSProperties = {
    width: "100%",
    borderCollapse: "collapse",
    border: "1px solid #ddd",
  };
  const thStyle: React.CSSProperties = {
    textAlign: "left",
    fontSize: 12,
    padding: "8px 10px",
    borderBottom: "1px solid #ddd",
    background: "#f6f6f6",
    whiteSpace: "nowrap",
  };
  const tdStyle: React.CSSProperties = {
    fontSize: 12,
    padding: "8px 10px",
    borderBottom: "1px solid #eee",
    verticalAlign: "top",
  };

  if (products.length === 0) {
    return (
      <div style={{ padding: 12, border: "1px solid #ddd" }}>
        <p style={{ margin: 0, fontSize: 12, color: "#555" }}>No products yet.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 12, border: "1px solid #ddd" }}>
      <div style={headerStyle}>
        <div>
          <p style={titleStyle}>Inventory Ledger</p>
          <div style={{ fontSize: 12, color: "#666" }}>
            Store: {storeId}
            {asOfUtcIso ? (
              <>
                {" "}
                • As-Of (UTC): <code>{asOfUtcIso}</code>
              </>
            ) : null}
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={labelStyle}>Product</label>
            <select
              value={selectedProductId ?? ""}
              onChange={(e) => setSelectedProductId(e.target.value ? Number(e.target.value) : null)}
              style={{ padding: 6, width: 260 }}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.sku} — {p.name}
                </option>
              ))}
            </select>
          </div>

          <button onClick={load} style={{ padding: "7px 10px", cursor: "pointer" }} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {error ? <div style={{ marginBottom: 10, color: "#b00020", fontSize: 12 }}>{error}</div> : null}

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Occurred (Local)</th>
            <th style={thStyle}>Type</th>
            <th style={thStyle}>Qty Δ</th>
            <th style={thStyle}>Unit Cost</th>
            <th style={thStyle}>Note</th>
            <th style={thStyle}>Recorded (Local)</th>
            <th style={thStyle}>Tx ID</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td style={tdStyle} colSpan={7}>
                {loading ? "Loading..." : "No transactions found."}
              </td>
            </tr>
          ) : (
            rows.map((tx) => (
              <tr key={tx.id}>
                <td style={tdStyle}>{tx.occurred_at ? utcIsoToLocalDisplay(tx.occurred_at) : ""}</td>
                <td style={tdStyle}>{tx.type}</td>
                <td style={tdStyle}>{tx.quantity_delta}</td>
                <td style={tdStyle}>{centsToDollars(tx.unit_cost_cents)}</td>
                <td style={tdStyle}>{tx.note ?? ""}</td>
                <td style={tdStyle}>{tx.created_at ? utcIsoToLocalDisplay(tx.created_at) : ""}</td>
                <td style={tdStyle}>{tx.id}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
