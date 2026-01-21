// Overview: React component for create product form UI.

import { useState } from "react";
import { apiPost } from "../lib/api";

type CreatedProduct = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
  store_id: number;
};

export function CreateProductForm({ onCreated }: { onCreated: () => void }) {
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [priceDollars, setPriceDollars] = useState(""); // UI input
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);

    const priceResult = validatePrice(priceDollars);
    if (!priceResult.valid) {
      setErr(priceResult.error!);
      return;
    }

    setSaving(true);
    try {
      await apiPost<CreatedProduct>("/api/products", {
        sku,
        name,
        price_cents: priceResult.cents,
        is_active: isActive,
      });
      setSku("");
      setName("");
      setPriceDollars("");
      setIsActive(true);
      onCreated(); // refresh list
    } catch (e: any) {
      setErr(e?.message ?? "Failed to create product");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="form-card" style={{ marginTop: 16 }}>
      <div className="form-title">Create Product</div>

      {err && (
        <div className="notice notice--error" style={{ marginBottom: 8 }}>
          {err}
        </div>
      )}

      <div className="form-row">
        <label className="form-stack">
          <span className="form-label">SKU</span>
          <input className="input" value={sku} onChange={(e) => setSku(e.target.value)} required />
        </label>

        <label className="form-stack">
          <span className="form-label">Name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <label className="form-stack">
          <span className="form-label">Price (USD)</span>
          <input
            className="input"
            value={priceDollars}
            onChange={(e) => setPriceDollars(e.target.value)}
            placeholder="12.99"
            inputMode="decimal"
          />
        </label>

        <label className="inline-toggle" style={{ marginTop: 22 }}>
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Active
        </label>

        <button type="submit" disabled={saving} className="btn btn--primary" style={{ marginTop: 18 }}>
          {saving ? "Saving..." : "Create"}
        </button>
      </div>
    </form>
  );
}
