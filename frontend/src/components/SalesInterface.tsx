// frontend/src/components/SalesInterface.tsx
import { useState, useEffect } from "react";
import { apiGet, apiPost } from "../lib/api";

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
};

type Sale = {
  id: number;
  document_number: string;
  status: string;
  store_id: number;
};

type SaleLine = {
  id: number;
  product_id: number;
  quantity: number;
  unit_price_cents: number;
  line_total_cents: number;
};

export function SalesInterface({ products }: { products: Product[] }) {
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [lines, setLines] = useState<SaleLine[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function createNewSale() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ sale: Sale }>("/api/sales/", { store_id: 1 });
      setCurrentSale(result.sale);
      setLines([]);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create sale");
    } finally {
      setLoading(false);
    }
  }

  async function addLineToSale() {
    if (!currentSale || !selectedProductId) return;

    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ line: SaleLine }>(
        `/api/sales/${currentSale.id}/lines`,
        { product_id: selectedProductId, quantity }
      );
      setLines([...lines, result.line]);
      setQuantity(1);
    } catch (e: any) {
      setError(e?.message ?? "Failed to add line");
    } finally {
      setLoading(false);
    }
  }

  async function postSale() {
    if (!currentSale) return;

    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ sale: Sale }>(`/api/sales/${currentSale.id}/post`, {});
      setCurrentSale(result.sale);
      alert(`Sale ${result.sale.document_number} posted successfully!`);
      // Reset
      setCurrentSale(null);
      setLines([]);
    } catch (e: any) {
      setError(e?.message ?? "Failed to post sale");
    } finally {
      setLoading(false);
    }
  }

  const total = lines.reduce((sum, line) => sum + line.line_total_cents, 0);

  return (
    <div style={{ marginTop: 20, padding: 12, border: "1px solid #ddd" }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
        Sales Interface (POS)
      </h3>

      {error && (
        <div style={{ padding: 8, background: "#fff5f5", color: "#9b1c1c", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {!currentSale ? (
        <button onClick={createNewSale} disabled={loading} style={{ padding: "8px 16px" }}>
          Start New Sale
        </button>
      ) : (
        <div>
          <div style={{ marginBottom: 12, padding: 8, background: "#f0f9ff", fontSize: 13 }}>
            <strong>Sale:</strong> {currentSale.document_number} | Status: {currentSale.status}
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <select
              value={selectedProductId ?? ""}
              onChange={(e) => setSelectedProductId(Number(e.target.value))}
              style={{ flex: 1, padding: 8 }}
            >
              <option value="">Select Product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} - ${p.price_cents ? (p.price_cents / 100).toFixed(2) : "N/A"}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              style={{ width: 80, padding: 8 }}
            />
            <button onClick={addLineToSale} disabled={loading || !selectedProductId} style={{ padding: "8px 16px" }}>
              Add
            </button>
          </div>

          {lines.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ddd" }}>
                    <th style={{ textAlign: "left", padding: 4 }}>Product</th>
                    <th style={{ textAlign: "right", padding: 4 }}>Qty</th>
                    <th style={{ textAlign: "right", padding: 4 }}>Price</th>
                    <th style={{ textAlign: "right", padding: 4 }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => {
                    const prod = products.find((p) => p.id === line.product_id);
                    return (
                      <tr key={line.id}>
                        <td style={{ padding: 4 }}>{prod?.name ?? "Unknown"}</td>
                        <td style={{ textAlign: "right", padding: 4 }}>{line.quantity}</td>
                        <td style={{ textAlign: "right", padding: 4 }}>
                          ${(line.unit_price_cents / 100).toFixed(2)}
                        </td>
                        <td style={{ textAlign: "right", padding: 4 }}>
                          ${(line.line_total_cents / 100).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ marginTop: 8, textAlign: "right", fontWeight: 600 }}>
                Total: ${(total / 100).toFixed(2)}
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={postSale}
              disabled={loading || lines.length === 0}
              style={{ padding: "8px 16px", background: "#10b981", color: "white", border: "none", cursor: "pointer" }}
            >
              Post Sale
            </button>
            <button
              onClick={() => {
                setCurrentSale(null);
                setLines([]);
              }}
              style={{ padding: "8px 16px" }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
