// Overview: React component for adjust inventory form UI.

import { useMemo, useState } from "react";
import { apiPost } from "../lib/api";
import { datetimeLocalToUtcIso } from "../lib/time";

type Product = {
  id: number;
  sku: string;
  name: string;
  store_id: number;
};

export function AdjustInventoryForm({
  products,
  storeId,
  onAdjusted,
}: {
  products: Product[];
  storeId: number;
  onAdjusted: () => void | Promise<void>;
}) {
  const activeProducts = useMemo(
    () => products.filter((p) => p.store_id === storeId),
    [products, storeId]
  );

  const [productId, setProductId] = useState<number | "">("");
  const [delta, setDelta] = useState<string>("-1");
  const [note, setNote] = useState<string>("");
  const [occurredAtLocal, setOccurredAtLocal] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function submit() {
    setErr(null);
    setOk(null);

    if (productId === "") {
      setErr("Pick a product.");
      return;
    }

    const d = Number(delta.trim());
    if (!Number.isFinite(d) || !Number.isInteger(d) || d === 0) {
      setErr("Adjustment must be a non-zero integer (e.g., -3 or 5).");
      return;
    }

    setSubmitting(true);
    try {
    const occurred_at = occurredAtLocal
      ? datetimeLocalToUtcIso(occurredAtLocal)
      : undefined;

    await apiPost("/api/inventory/adjust", {
      store_id: storeId,
      product_id: productId,
      quantity_delta: d,
      note: note.trim() ? note.trim() : undefined,
      occurred_at,
    });

      setOk("Adjusted.");
      setDelta("-1");
      setNote("");
      setOccurredAtLocal("");
      await onAdjusted();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to adjust inventory.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        border: "1px solid #eee",
        borderRadius: 8,
        background: "#fff",
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
        Manual Adjustment
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#444" }}>Product</label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : "")}
            style={{ padding: 6, minWidth: 260 }}
          >
            <option value="">Select…</option>
            {activeProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#444" }}>Quantity Delta</label>
          <input
            value={delta}
            onChange={(e) => setDelta(e.target.value)}
            inputMode="numeric"
            style={{ padding: 6, width: 140 }}
          />
        </div>
        
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#444" }}>Occurred At (optional)</label>
          <input
            type="datetime-local"
            value={occurredAtLocal}
            onChange={(e) => setOccurredAtLocal(e.target.value)}
            style={{ padding: 6, width: 200 }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 220 }}>
          <label style={{ fontSize: 12, color: "#444" }}>Note (optional)</label>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="reason for adjustment"
            style={{ padding: 6, width: "100%" }}
          />
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          style={{ padding: "8px 12px", cursor: "pointer" }}
        >
          {submitting ? "Adjusting…" : "Adjust"}
        </button>
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
        Use a negative number to reduce on-hand (e.g., -2). Adjustments cannot make on-hand negative.
      </div>

      {err && <div style={{ marginTop: 10, color: "#9b1c1c" }}>{err}</div>}
      {ok && <div style={{ marginTop: 10, color: "#1f7a1f" }}>{ok}</div>}
    </div>
  );
}
