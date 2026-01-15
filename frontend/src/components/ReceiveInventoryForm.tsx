import { useMemo, useState } from "react";
import { apiPost } from "../lib/api";
import { datetimeLocalToUtcIso } from "../lib/time";

type Product = {
  id: number;
  sku: string;
  name: string;
  store_id: number;
};

export function ReceiveInventoryForm({
  products,
  storeId,
  onReceived,
}: {
  products: Product[];
  storeId: number;
  onReceived: () => void | Promise<void>;
}) {
  const activeProducts = useMemo(
    () => products.filter((p) => p.store_id === storeId),
    [products, storeId]
  );

  const [productId, setProductId] = useState<number | "">("");
  const [qty, setQty] = useState<string>("1");
  const [unitCostUsd, setUnitCostUsd] = useState<string>("");
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

    const q = Number(qty.trim());
    if (!Number.isFinite(q) || !Number.isInteger(q) || q <= 0) {
      setErr("Quantity must be a positive integer.");
      return;
    }

    const c = Number(unitCostUsd.trim());
    if (!Number.isFinite(c) || c < 0) {
      setErr("Unit cost must be a number (>= 0).");
      return;
    }

    const unit_cost_cents = Math.round(c * 100);

    setSubmitting(true);
    try {
      const occurred_at = occurredAtLocal
        ? datetimeLocalToUtcIso(occurredAtLocal)
        : undefined;

      await apiPost("/api/inventory/receive", {
        store_id: storeId,
        product_id: productId,
        quantity_delta: q,
        unit_cost_cents,
        note: note.trim() ? note.trim() : undefined,
        occurred_at,
      });


      setOk("Received.");
      setQty("1");
      setUnitCostUsd("");
      setNote("");
      setOccurredAtLocal("");

      await onReceived();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to receive inventory.");
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
        Receive Inventory
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
          <label style={{ fontSize: 12, color: "#444" }}>Quantity</label>
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputMode="numeric"
            style={{ padding: 6, width: 120 }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: 12, color: "#444" }}>Unit Cost (USD)</label>
          <input
            value={unitCostUsd}
            onChange={(e) => setUnitCostUsd(e.target.value)}
            placeholder="2.50"
            inputMode="decimal"
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
            placeholder="invoice #, vendor, etc."
            style={{ padding: 6, width: "100%" }}
          />
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          style={{ padding: "8px 12px", cursor: "pointer" }}
        >
          {submitting ? "Receiving…" : "Receive"}
        </button>
      </div>

      {err && <div style={{ marginTop: 10, color: "#9b1c1c" }}>{err}</div>}
      {ok && <div style={{ marginTop: 10, color: "#1f7a1f" }}>{ok}</div>}
    </div>
  );
}
