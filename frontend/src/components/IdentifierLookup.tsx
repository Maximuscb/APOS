// frontend/src/components/IdentifierLookup.tsx
import { useState } from "react";
import { apiGet, apiPost } from "../lib/api";

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
};

export function IdentifierLookup() {
  const [barcode, setBarcode] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [addForm, setAddForm] = useState({
    product_id: "",
    type: "",
    value: "",
    vendor_id: "",
    is_primary: false,
  });
  const [addStatus, setAddStatus] = useState<string | null>(null);

  async function handleLookup() {
    if (!barcode.trim()) return;

    setLoading(true);
    setError(null);
    setProduct(null);

    try {
      const result = await apiGet<{ product: Product }>(`/api/identifiers/lookup/${encodeURIComponent(barcode)}`);
      setProduct(result.product);
    } catch (e: any) {
      setError(e?.message ?? "Product not found");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddIdentifier() {
    if (!addForm.product_id || !addForm.type || !addForm.value) return;
    setLoading(true);
    setError(null);
    setAddStatus(null);
    try {
      await apiPost("/api/identifiers/", {
        product_id: Number(addForm.product_id),
        type: addForm.type,
        value: addForm.value,
        vendor_id: addForm.vendor_id ? Number(addForm.vendor_id) : null,
        is_primary: addForm.is_primary,
      });
      setAddStatus("Identifier added.");
      setAddForm({ product_id: "", type: "", value: "", vendor_id: "", is_primary: false });
    } catch (e: any) {
      setError(e?.message ?? "Failed to add identifier");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pos-card">
      <h3>Identifier Lookup</h3>
      <p className="muted">Scan or type a barcode, SKU, or UPC to find a product.</p>

      <div className="pos-form-row">
        <input
          className="input"
          type="text"
          placeholder="Scan or type barcode/SKU/UPC"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLookup()}
        />
        <button className="btn btn--primary" onClick={handleLookup} disabled={loading}>
          {loading ? "Looking up..." : "Lookup"}
        </button>
      </div>

      {error && <div className="alert">{error}</div>}

      {product && (
        <div className="pos-result">
          <div>
            <strong>Found:</strong> {product.name}
          </div>
          <div>
            SKU: {product.sku} | ID: {product.id}
          </div>
          <div>Price: ${product.price_cents ? (product.price_cents / 100).toFixed(2) : "N/A"}</div>
        </div>
      )}

      <div className="pos-divider" />
      <h4 className="pos-section-title">Add Identifier</h4>
      {addStatus && <div className="pos-success">{addStatus}</div>}
      <div className="pos-form">
        <input
          className="input"
          type="number"
          placeholder="Product ID"
          value={addForm.product_id}
          onChange={(e) => setAddForm({ ...addForm, product_id: e.target.value })}
        />
        <input
          className="input"
          type="text"
          placeholder="Identifier type (SKU, UPC, etc.)"
          value={addForm.type}
          onChange={(e) => setAddForm({ ...addForm, type: e.target.value })}
        />
        <input
          className="input"
          type="text"
          placeholder="Identifier value"
          value={addForm.value}
          onChange={(e) => setAddForm({ ...addForm, value: e.target.value })}
        />
        <input
          className="input"
          type="number"
          placeholder="Vendor ID (optional)"
          value={addForm.vendor_id}
          onChange={(e) => setAddForm({ ...addForm, vendor_id: e.target.value })}
        />
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={addForm.is_primary}
            onChange={(e) => setAddForm({ ...addForm, is_primary: e.target.checked })}
          />
          Primary identifier
        </label>
        <button className="btn btn--ghost" onClick={handleAddIdentifier} disabled={loading}>
          {loading ? "Saving..." : "Add Identifier"}
        </button>
      </div>
    </div>
  );
}
