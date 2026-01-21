// Overview: React component for receive inventory form UI.

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, getAuthToken } from "../lib/api";
import { datetimeLocalToUtcIso } from "../lib/time";

type Product = {
  id: number;
  sku: string;
  name: string;
  store_id: number;
};

type Vendor = {
  id: number;
  name: string;
  code: string | null;
};

type IdentifierLookupResponse = {
  product?: Product;
  products?: Product[];
  ambiguous?: boolean;
  error?: string;
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
  const [vendorId, setVendorId] = useState<number | "">("");
  const [receiveType, setReceiveType] = useState<string>("PURCHASE");
  const [qty, setQty] = useState<string>("1");
  const [unitCostUsd, setUnitCostUsd] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [occurredAtLocal, setOccurredAtLocal] = useState<string>("");
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [receiveTypes, setReceiveTypes] = useState<string[]>([]);
  const [loadingVendors, setLoadingVendors] = useState(false);

  const [scanValue, setScanValue] = useState("");
  const [scanResults, setScanResults] = useState<Product[]>([]);
  const [scanConflict, setScanConflict] = useState<Product[] | null>(null);
  const [scanLoading, setScanLoading] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadVendors() {
      setLoadingVendors(true);
      try {
        const result = await apiGet<{ items: Vendor[] }>("/api/vendors");
        if (isMounted) {
          setVendors(result.items ?? []);
        }
      } catch (e: any) {
        if (isMounted) {
          setErr(e?.message ?? "Failed to load vendors.");
        }
      } finally {
        if (isMounted) {
          setLoadingVendors(false);
        }
      }
    }

    async function loadReceiveTypes() {
      try {
        const result = await apiGet<{ types: string[] }>("/api/receives/types");
        if (isMounted) {
          setReceiveTypes(result.types ?? []);
          if (result.types?.length) {
            setReceiveType(result.types[0]);
          }
        }
      } catch {
        // fallback to defaults
      }
    }

    loadVendors();
    loadReceiveTypes();

    return () => {
      isMounted = false;
    };
  }, []);

  async function lookupIdentifier(value: string) {
    if (!value.trim()) {
      return;
    }

    setScanLoading(true);
    setScanResults([]);
    setScanConflict(null);
    setErr(null);

    try {
      const token = getAuthToken();
      const res = await fetch(`/api/identifiers/lookup/${encodeURIComponent(value)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = (await res.json()) as IdentifierLookupResponse;

      if (res.status === 409 && data.products) {
        setScanConflict(data.products);
        return;
      }

      if (!res.ok) {
        setErr(data?.error ?? "Lookup failed.");
        return;
      }

      if (data.product) {
        setScanResults([data.product]);
      }
    } catch (e: any) {
      setErr(e?.message ?? "Lookup failed.");
    } finally {
      setScanLoading(false);
    }
  }

  async function submit() {
    setErr(null);
    setOk(null);

    if (vendorId === "") {
      setErr("Pick a vendor.");
      return;
    }

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

      const receiveDoc = await apiPost<{ id: number }>("/api/receives", {
        store_id: storeId,
        vendor_id: vendorId,
        receive_type: receiveType,
        note: note.trim() ? note.trim() : undefined,
        occurred_at,
      });

      await apiPost(`/api/receives/${receiveDoc.id}/lines`, {
        product_id: productId,
        quantity: q,
        unit_cost_cents,
        note: note.trim() ? note.trim() : undefined,
      });

      await apiPost(`/api/receives/${receiveDoc.id}/approve`, {});
      await apiPost(`/api/receives/${receiveDoc.id}/post`, {});

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
    <div className="form-card" style={{ marginTop: 12 }}>
      <div className="form-title">Receive Inventory</div>

      <div className="form-row">
        <div className="form-stack">
          <label className="form-label">Vendor</label>
          <select
            value={vendorId}
            onChange={(e) => setVendorId(e.target.value ? Number(e.target.value) : "")}
            className="select"
            style={{ minWidth: 240 }}
            disabled={loadingVendors}
          >
            <option value="">
              {loadingVendors ? "Loading vendors..." : "Select vendor"}
            </option>
            {vendors.map((vendor) => (
              <option key={vendor.id} value={vendor.id}>
                {vendor.name}
                {vendor.code ? ` (${vendor.code})` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="form-stack">
          <label className="form-label">Receive Type</label>
          <select
            value={receiveType}
            onChange={(e) => setReceiveType(e.target.value)}
            className="select"
            style={{ minWidth: 180 }}
          >
            {receiveTypes.length ? (
              receiveTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))
            ) : (
              <>
                <option value="PURCHASE">PURCHASE</option>
                <option value="DONATION">DONATION</option>
                <option value="FOUND">FOUND</option>
                <option value="TRANSFER_IN">TRANSFER_IN</option>
                <option value="OTHER">OTHER</option>
              </>
            )}
          </select>
        </div>

        <div className="form-stack">
          <label className="form-label">Scan/Search Identifier</label>
          <div className="form-actions">
            <input
              value={scanValue}
              onChange={(e) => setScanValue(e.target.value)}
              placeholder="Scan barcode or enter SKU"
              className="input"
              style={{ minWidth: 220 }}
            />
            <button
              type="button"
              onClick={() => lookupIdentifier(scanValue)}
              disabled={scanLoading}
              className="btn btn--ghost btn--sm"
            >
              {scanLoading ? "Searching..." : "Search"}
            </button>
          </div>
        </div>

        <div className="form-stack">
          <label className="form-label">Product</label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : "")}
            className="select"
            style={{ minWidth: 260 }}
          >
            <option value="">Select</option>
            {activeProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
        </div>

        <div className="form-stack">
          <label className="form-label">Quantity</label>
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            inputMode="numeric"
            className="input"
            style={{ width: 120 }}
          />
        </div>

        <div className="form-stack">
          <label className="form-label">Unit Cost (USD)</label>
          <input
            value={unitCostUsd}
            onChange={(e) => setUnitCostUsd(e.target.value)}
            placeholder="2.50"
            inputMode="decimal"
            className="input"
            style={{ width: 140 }}
          />
        </div>

        <div className="form-stack">
          <label className="form-label">Occurred At (optional)</label>
          <input
            type="datetime-local"
            value={occurredAtLocal}
            onChange={(e) => setOccurredAtLocal(e.target.value)}
            className="input"
            style={{ width: 200 }}
          />
        </div>

        <div className="form-stack" style={{ flex: 1, minWidth: 220 }}>
          <label className="form-label">Note (optional)</label>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="invoice #, vendor, etc."
            className="input"
            style={{ width: "100%" }}
          />
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          className="btn btn--primary"
        >
          {submitting ? "Receiving..." : "Receive"}
        </button>
      </div>

      {scanResults.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="helper-text" style={{ fontWeight: 600, marginBottom: 6 }}>
            Search Results
          </div>
          <div className="form-actions">
            {scanResults.map((result) => (
              <button
                key={result.id}
                type="button"
                onClick={() => setProductId(result.id)}
                className="btn btn--ghost btn--sm"
              >
                {result.name} ({result.sku})
              </button>
            ))}
          </div>
        </div>
      )}

      {scanConflict && scanConflict.length > 0 && (
        <div className="notice notice--error" style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
            Multiple matches found. Select the correct product.
          </div>
          <div className="form-actions">
            {scanConflict.map((result) => (
              <button
                key={result.id}
                type="button"
                onClick={() => {
                  setProductId(result.id);
                  setScanConflict(null);
                }}
                className="btn btn--ghost btn--sm"
              >
                {result.name} ({result.sku})
              </button>
            ))}
          </div>
        </div>
      )}

      {err && (
        <div className="notice notice--error" style={{ marginTop: 10 }}>
          {err}
        </div>
      )}
      {ok && (
        <div className="notice notice--success" style={{ marginTop: 10 }}>
          {ok}
        </div>
      )}
    </div>
  );
}
