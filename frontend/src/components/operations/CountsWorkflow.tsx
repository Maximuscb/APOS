import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

type Product = {
  id: number;
  sku: string;
  name: string;
};

type Count = {
  id: number;
  store_id: number;
  count_type: string;
  status: string;
  reason: string | null;
  created_at: string;
  lines?: CountLine[];
};

type CountLine = {
  id: number;
  product_id: number;
  expected_quantity: number;
  actual_quantity: number;
  variance: number;
  product_name?: string;
};

type Props = {
  storeId: number;
  isAuthed: boolean;
};

export function CountsWorkflow({ storeId, isAuthed }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Products for picker
  const [products, setProducts] = useState<Product[]>([]);

  // List of counts
  const [counts, setCounts] = useState<Count[]>([]);
  const [showPendingOnly, setShowPendingOnly] = useState(true);

  // Count creation
  const [countType, setCountType] = useState<"CYCLE" | "FULL">("CYCLE");
  const [reason, setReason] = useState("");
  const [activeCountId, setActiveCountId] = useState<number | null>(null);

  // Adding items to active count
  const [selectedProductId, setSelectedProductId] = useState<number | "">("");
  const [actualQuantity, setActualQuantity] = useState("");

  // Selected count for details
  const [selectedCount, setSelectedCount] = useState<Count | null>(null);

  async function loadProducts() {
    try {
      const result = await apiGet<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
      setProducts(result.items ?? []);
    } catch (e: any) {
      console.error("Failed to load products:", e);
    }
  }

  async function loadCounts() {
    if (!isAuthed) return;
    setLoading(true);
    try {
      const url = showPendingOnly ? `/api/counts/pending` : `/api/counts?store_id=${storeId}`;
      const result = await apiGet<{ counts: Count[] }>(url);
      setCounts(result.counts ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load counts");
    } finally {
      setLoading(false);
    }
  }

  async function createCount() {
    setError(null);
    setNotice(null);

    try {
      const result = await apiPost<{ count: Count }>("/api/counts", {
        store_id: storeId,
        count_type: countType,
        reason: reason || undefined,
      });

      setActiveCountId(result.count.id);
      setNotice(`Count #${result.count.id} created. Add items to count.`);
      setReason("");
      loadCounts();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create count");
    }
  }

  async function addCountLine() {
    if (!activeCountId || !selectedProductId || !actualQuantity) return;
    setError(null);

    try {
      await apiPost(`/api/counts/${activeCountId}/lines`, {
        product_id: selectedProductId,
        actual_quantity: parseInt(actualQuantity),
      });
      setNotice("Item added to count");
      setSelectedProductId("");
      setActualQuantity("");
      // Reload count details
      await loadCountDetails(activeCountId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to add count line");
    }
  }

  async function loadCountDetails(countId: number) {
    try {
      const result = await apiGet<{ count: Count }>(`/api/counts/${countId}`);
      setSelectedCount(result.count);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load count details");
    }
  }

  async function performAction(countId: number, action: string, data?: Record<string, any>) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/counts/${countId}/${action}`, data ?? {});
      setNotice(`Count ${action} successfully`);
      if (action === "post" || action === "cancel") {
        setActiveCountId(null);
      }
      loadCounts();
      setSelectedCount(null);
    } catch (e: any) {
      setError(e?.message ?? `Failed to ${action} count`);
    }
  }

  function finishCounting() {
    setActiveCountId(null);
    setNotice("Finished adding items. You can now approve and post the count.");
  }

  useEffect(() => {
    loadProducts();
    loadCounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthed, showPendingOnly, storeId]);

  if (!isAuthed) {
    return <p className="muted">Sign in to manage inventory counts.</p>;
  }

  const getProductName = (id: number) => {
    const p = products.find((p) => p.id === id);
    return p ? `${p.sku} - ${p.name}` : `Product #${id}`;
  };

  return (
    <div>
      {error && <div className="alert">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}

      {/* Create count or add to active count */}
      <div style={{ marginBottom: 16, padding: 12, border: "1px solid #ddd", background: "#f9f9f9" }}>
        {!activeCountId ? (
          <>
            <h4>Start New Count</h4>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span>Count Type</span>
                <select value={countType} onChange={(e) => setCountType(e.target.value as "CYCLE" | "FULL")}>
                  <option value="CYCLE">Cycle Count</option>
                  <option value="FULL">Full Inventory</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span>Reason</span>
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Optional"
                />
              </label>
              <button onClick={createCount} className="btn btn--primary">
                Start Count
              </button>
            </div>
          </>
        ) : (
          <>
            <h4>Active Count #{activeCountId}</h4>
            <p className="muted">Add products and their actual quantities.</p>

            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <select value={selectedProductId} onChange={(e) => setSelectedProductId(Number(e.target.value))}>
                <option value="">Select product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} - {p.name}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={0}
                value={actualQuantity}
                onChange={(e) => setActualQuantity(e.target.value)}
                placeholder="Actual qty"
                style={{ width: 100 }}
              />
              <button onClick={addCountLine} disabled={!selectedProductId || !actualQuantity}>
                Add Item
              </button>
            </div>

            {selectedCount && selectedCount.lines && selectedCount.lines.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong>Items counted ({selectedCount.lines.length}):</strong>
                <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 4 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Product</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Expected</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Actual</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCount.lines.map((line) => (
                      <tr key={line.id}>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>
                          {line.product_name || getProductName(line.product_id)}
                        </td>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>{line.expected_quantity}</td>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>{line.actual_quantity}</td>
                        <td
                          style={{
                            padding: 4,
                            borderBottom: "1px solid #eee",
                            color: line.variance !== 0 ? (line.variance > 0 ? "green" : "red") : "inherit",
                          }}
                        >
                          {line.variance > 0 ? "+" : ""}
                          {line.variance}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
              <button onClick={finishCounting} className="btn btn--primary">
                Done Adding Items
              </button>
              <button onClick={() => performAction(activeCountId, "cancel")} className="btn btn--ghost">
                Cancel Count
              </button>
            </div>
          </>
        )}
      </div>

      {/* Counts list */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h4>Counts ({counts.length})</h4>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={showPendingOnly}
              onChange={(e) => setShowPendingOnly(e.target.checked)}
            />
            Pending only
          </label>
        </div>

        {loading ? (
          <p>Loading...</p>
        ) : counts.length === 0 ? (
          <p className="muted">No counts found.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>ID</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Type</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Status</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Reason</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Created</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {counts.map((c) => (
                <tr key={c.id}>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{c.id}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{c.count_type}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: 4,
                        fontSize: 12,
                        background:
                          c.status === "PENDING"
                            ? "#fff3cd"
                            : c.status === "APPROVED"
                              ? "#d4edda"
                              : c.status === "POSTED"
                                ? "#cce5ff"
                                : "#f8d7da",
                      }}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{c.reason || "-"}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      <button onClick={() => loadCountDetails(c.id)} style={{ padding: "2px 6px", fontSize: 12 }}>
                        View
                      </button>
                      {c.status === "PENDING" && (
                        <>
                          <button
                            onClick={() => {
                              setActiveCountId(c.id);
                              loadCountDetails(c.id);
                            }}
                            style={{ padding: "2px 6px", fontSize: 12 }}
                          >
                            Add Items
                          </button>
                          <button onClick={() => performAction(c.id, "approve")} style={{ padding: "2px 6px", fontSize: 12 }}>
                            Approve
                          </button>
                          <button onClick={() => performAction(c.id, "cancel")} style={{ padding: "2px 6px", fontSize: 12 }}>
                            Cancel
                          </button>
                        </>
                      )}
                      {c.status === "APPROVED" && (
                        <button onClick={() => performAction(c.id, "post")} style={{ padding: "2px 6px", fontSize: 12 }}>
                          Post
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Count details modal */}
      {selectedCount && !activeCountId && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setSelectedCount(null)}
        >
          <div
            style={{ background: "white", padding: 24, borderRadius: 8, maxWidth: 600, width: "90%" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Count #{selectedCount.id}</h3>
            <p><strong>Type:</strong> {selectedCount.count_type}</p>
            <p><strong>Status:</strong> {selectedCount.status}</p>
            <p><strong>Reason:</strong> {selectedCount.reason || "None"}</p>
            <p><strong>Created:</strong> {new Date(selectedCount.created_at).toLocaleString()}</p>

            {selectedCount.lines && selectedCount.lines.length > 0 && (
              <>
                <h4>Count Lines</h4>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Product</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Expected</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Actual</th>
                      <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCount.lines.map((line) => (
                      <tr key={line.id}>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>
                          {line.product_name || getProductName(line.product_id)}
                        </td>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>{line.expected_quantity}</td>
                        <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>{line.actual_quantity}</td>
                        <td
                          style={{
                            padding: 4,
                            borderBottom: "1px solid #eee",
                            fontWeight: line.variance !== 0 ? "bold" : "normal",
                            color: line.variance !== 0 ? (line.variance > 0 ? "green" : "red") : "inherit",
                          }}
                        >
                          {line.variance > 0 ? "+" : ""}
                          {line.variance}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <button onClick={() => setSelectedCount(null)} style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
