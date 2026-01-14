// frontend/src/components/IdentifierLookup.tsx
import { useState } from "react";
import { apiGet } from "../lib/api";

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

  return (
    <div style={{ marginTop: 20, padding: 12, border: "1px solid #ddd" }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
        Identifier Lookup (Barcode Scanner)
      </h3>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          placeholder="Scan or type barcode/SKU/UPC"
          value={barcode}
          onChange={(e) => setBarcode(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLookup()}
          style={{ flex: 1, padding: 8, fontSize: 14 }}
        />
        <button onClick={handleLookup} disabled={loading} style={{ padding: "8px 16px" }}>
          {loading ? "Looking up..." : "Lookup"}
        </button>
      </div>

      {error && (
        <div style={{ padding: 8, background: "#fff5f5", color: "#9b1c1c", fontSize: 13 }}>
          {error}
        </div>
      )}

      {product && (
        <div style={{ padding: 8, background: "#f0fdf4", fontSize: 13 }}>
          <div><strong>Found:</strong> {product.name}</div>
          <div>SKU: {product.sku} | ID: {product.id}</div>
          <div>Price: ${product.price_cents ? (product.price_cents / 100).toFixed(2) : "N/A"}</div>
        </div>
      )}
    </div>
  );
}
