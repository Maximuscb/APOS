// Overview: React component for sales interface UI.

// frontend/src/components/SalesInterface.tsx
import { useState } from "react";
import { apiPost } from "../lib/api";

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

export function SalesInterface({
  products,
  storeId,
  isAuthed,
  registerId,
  sessionId,
}: {
  products: Product[];
  storeId: number;
  isAuthed: boolean;
  registerId?: number | null;
  sessionId?: number | null;
}) {
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [lines, setLines] = useState<SaleLine[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function createNewSale() {
    if (!isAuthed) {
      setError("Login required to create a sale.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { store_id: storeId };
      if (registerId) payload.register_id = registerId;
      if (sessionId) payload.register_session_id = sessionId;
      const result = await apiPost<{ sale: Sale }>("/api/sales/", payload);
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
      // Upsert: replace existing line if present, otherwise append
      setLines((prev) => {
        const idx = prev.findIndex((l) => l.id === result.line.id);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = result.line;
          return updated;
        }
        return [...prev, result.line];
      });
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
    <div className="pos">
      <div className="pos__header">
        <div>
          <div className="pos__eyebrow">Store {storeId}</div>
          <h3>Sales Terminal</h3>
          <p className="muted">Open a sale, scan items, and post when tender is complete.</p>
        </div>
        <div className="pos__header-actions">
          {currentSale ? (
            <div className="pos__status">
              <span className="chip">{currentSale.status}</span>
              <span className="chip">Doc {currentSale.document_number}</span>
            </div>
          ) : (
            <span className="chip">No active sale</span>
          )}
          <button className="btn btn--ghost" onClick={createNewSale} disabled={loading || !isAuthed}>
            New sale
          </button>
        </div>
      </div>

      {!isAuthed && <div className="alert">Login required to create and post sales.</div>}

      {error && <div className="alert">{error}</div>}

      {!currentSale ? (
        <div className="pos__empty">
          <div className="pos__empty-card">
            <div className="pos__empty-title">Start a sale to unlock the register.</div>
            <p className="muted">Create a new sale, then add items and post.</p>
            <button className="btn btn--primary" onClick={createNewSale} disabled={loading || !isAuthed}>
              Open new sale
            </button>
          </div>
        </div>
      ) : (
        <div className="pos__body">
          <div className="pos__left">
            <div className="pos__add">
              <select
                className="input"
                value={selectedProductId ?? ""}
                onChange={(e) => setSelectedProductId(Number(e.target.value))}
              >
                <option value="">Select product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} - ${p.price_cents ? (p.price_cents / 100).toFixed(2) : "N/A"}
                  </option>
                ))}
              </select>
              <input
                className="input"
                type="number"
                min="1"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              />
              <button
                className="btn btn--primary"
                onClick={addLineToSale}
                disabled={loading || !selectedProductId}
              >
                Add item
              </button>
            </div>

            <div className="pos__cart">
              <div className="pos__cart-header">
                <span>Item</span>
                <span>Qty</span>
                <span>Price</span>
                <span>Total</span>
              </div>
              {lines.length === 0 ? (
                <div className="pos__cart-empty muted">No items in cart yet.</div>
              ) : (
                lines.map((line) => {
                  const prod = products.find((p) => p.id === line.product_id);
                  return (
                    <div key={line.id} className="pos__cart-row">
                      <span>{prod?.name ?? "Unknown"}</span>
                      <span>{line.quantity}</span>
                      <span>${(line.unit_price_cents / 100).toFixed(2)}</span>
                      <span>${(line.line_total_cents / 100).toFixed(2)}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="pos__right">
            <div className="pos__summary">
              <div className="pos__summary-row">
                <span>Items</span>
                <span>{lines.reduce((sum, line) => sum + line.quantity, 0)}</span>
              </div>
              <div className="pos__summary-row">
                <span>Subtotal</span>
                <span>${(total / 100).toFixed(2)}</span>
              </div>
              <div className="pos__summary-total">
                <span>Total due</span>
                <span>${(total / 100).toFixed(2)}</span>
              </div>
            </div>
            <div className="pos__hint muted">
              Posting a sale requires on-hand stock and a received cost basis for each item.
            </div>
            <div className="pos__actions">
              <button
                className="btn btn--primary"
                onClick={postSale}
                disabled={loading || lines.length === 0}
              >
                Post sale
              </button>
              <button
                className="btn btn--ghost"
                onClick={() => {
                  setCurrentSale(null);
                  setLines([]);
                }}
              >
                Cancel sale
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
