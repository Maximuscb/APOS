// Overview: React component for products table UI.

import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../lib/api";
import { datetimeLocalToUtcIso } from "../lib/time";

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
  store_id: number;
};

type ProductPatch = {
  name: string;
  price_cents: number | null;
  is_active: boolean;
};

type InventorySummary = {
  store_id: number;
  product_id: number;
  quantity_on_hand: number;
  weighted_average_cost_cents: number | null;
  recent_unit_cost_cents: number | null;
};

export function ProductsTable({
  products,
  onDelete,
  onUpdate,
  asOf,
  storeId,
}: {
  products: Product[];
  onDelete: (id: number) => void;
  onUpdate: (id: number, patch: ProductPatch) => Promise<void> | void;
  asOf: string; // "" or ISO-like string
  storeId: number;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [priceUsd, setPriceUsd] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rowErr, setRowErr] = useState<string | null>(null);
  const asOfUtcIso = useMemo(() => datetimeLocalToUtcIso(asOf), [asOf]);


  const [invByProductId, setInvByProductId] = useState<Record<number, InventorySummary>>({});

  function startEdit(p: Product) {
    setEditingId(p.id);
    setName(p.name);
    setPriceUsd(p.price_cents == null ? "" : (p.price_cents / 100).toFixed(2));
                    "-"
    setRowErr(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setRowErr(null);
    setSaving(false);
  }

  // Maximum price in cents - must match backend MAX_PRICE_CENTS
  const MAX_PRICE_CENTS = 999_999_999; // $9,999,999.99

  function validatePrice(input: string): { valid: boolean; cents: number | null; error?: string } {
    const s = input.trim();
    if (!s) return { valid: true, cents: null };

    // Reject scientific notation (e.g., "1e15", "1E10")
    if (/[eE]/.test(s)) {
      return { valid: false, cents: null, error: "Scientific notation is not allowed" };
    }

    const n = parseFloat(s);
    if (!Number.isFinite(n)) {
      return { valid: false, cents: null, error: "Price must be a valid number" };
    }
    if (n < 0) {
      return { valid: false, cents: null, error: "Price cannot be negative" };
    }

    const cents = Math.round(n * 100);
    if (cents > MAX_PRICE_CENTS) {
      return { valid: false, cents: null, error: `Price cannot exceed $${(MAX_PRICE_CENTS / 100).toLocaleString()}` };
    }

    return { valid: true, cents };
  }

  async function saveEdit(id: number) {
    setRowErr(null);

    const trimmed = name.trim();
    if (!trimmed) {
      setRowErr("Name cannot be blank.");
      return;
    }

    const priceResult = validatePrice(priceUsd);
    if (!priceResult.valid) {
      setRowErr(priceResult.error!);
      return;
    }

    setSaving(true);
    try {
      await onUpdate(id, { name: trimmed, price_cents: priceResult.cents, is_active: isActive });
      cancelEdit();
    } catch (e: any) {
      setRowErr(e?.message ?? "Failed to save.");
      setSaving(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadSummaries() {
      const next: Record<number, InventorySummary> = {};
      const qs = asOfUtcIso ? `&as_of=${encodeURIComponent(asOfUtcIso)}` : "";

      for (const p of products) {
        try {
          const s = await apiGet<InventorySummary>(
            `/api/inventory/${p.id}/summary?store_id=${storeId}${qs}`
          );
          next[p.id] = s;
        } catch {
          // ignore per-row summary errors; keep UI usable
        }
      }

      if (!cancelled) setInvByProductId(next);
    }

    if (products.length) loadSummaries();
    else setInvByProductId({});

    return () => {
      cancelled = true;
    };
  }, [products, asOfUtcIso, storeId]);

  return (
    <table className="data-table">
      <thead>
        <tr>
          {["SKU", "Name", "Price", "On Hand", "WAC", "Recent Cost", "Active", "Actions"].map(
            (h) => (
              <th key={h}>
                {h}
              </th>
            )
          )}
        </tr>
      </thead>

      <tbody>
        {products.length === 0 ? (
          <tr>
            <td colSpan={8}>
              No products.
            </td>
          </tr>
        ) : (
          products.map((p) => {
            const editing = editingId === p.id;
            const inv = invByProductId[p.id];
            const wac = inv?.weighted_average_cost_cents;
            const recent = inv?.recent_unit_cost_cents;

            return (
              <tr key={p.id}>
                <td style={{ fontFamily: "monospace" }}>
                  {p.sku}
                </td>

                <td>
                  {editing ? (
                    <input
                      className="input"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      style={{ width: "100%" }}
                    />
                  ) : (
                    p.name
                  )}
                </td>

                <td>
                  {editing ? (
                    <input
                      className="input"
                      value={priceUsd}
                      onChange={(e) => setPriceUsd(e.target.value)}
                      placeholder="12.99"
                      inputMode="decimal"
                      style={{ width: 120 }}
                    />
                  ) : p.price_cents == null ? (
                    "-"
                  ) : (
                    `$${(p.price_cents / 100).toFixed(2)}`
                  )}
                </td>

                <td>
                  {inv?.quantity_on_hand ?? "-"}
                </td>

                <td>
                  {wac == null ? "-" : `$${(wac / 100).toFixed(2)}`}
                </td>

                <td>
                  {recent == null ? "-" : `$${(recent / 100).toFixed(2)}`}
                </td>

                <td>
                  {editing ? (
                    <label className="inline-toggle">
                      <input
                        type="checkbox"
                        checked={isActive}
                        onChange={(e) => setIsActive(e.target.checked)}
                      />
                      Active
                    </label>
                  ) : p.is_active ? (
                    "Yes"
                  ) : (
                    "No"
                  )}
                </td>

                <td>
                  {editing ? (
                    <div className="form-actions">
                      <button
                        onClick={() => saveEdit(p.id)}
                        disabled={saving}
                        className="btn btn--primary btn--sm"
                      >
                        {saving ? "Saving..." : "Save"}
                      </button>
                      <button
                        onClick={cancelEdit}
                        disabled={saving}
                        className="btn btn--ghost btn--sm"
                      >
                        Cancel
                      </button>
                      {rowErr && <span className="text-error">{rowErr}</span>}
                    </div>
                  ) : (
                    <div className="form-actions">
                      <button
                        onClick={() => startEdit(p)}
                        className="btn btn--ghost btn--sm"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDelete(p.id)}
                        className="btn btn--warn btn--sm"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })
        )}
      </tbody>
    </table>
  );
}
