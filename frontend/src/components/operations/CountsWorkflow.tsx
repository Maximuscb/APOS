// Overview: React workflow component for counts workflow operations.

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
      <div className="form-card" style={{ marginBottom: 16 }}>
        {!activeCountId ? (
          <>
            <h4>Start New Count</h4>
            <div className="form-row">
              <label className="form-stack">
                <span className="form-label">Count Type</span>
                <select
                  className="select"
                  value={countType}
                  onChange={(e) => setCountType(e.target.value as "CYCLE" | "FULL")}
                >
                  <option value="CYCLE">Cycle Count</option>
                  <option value="FULL">Full Inventory</option>
                </select>
              </label>
              <label className="form-stack">
                <span className="form-label">Reason</span>
                <input
                  className="input"
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

            <div className="form-actions" style={{ marginTop: 8 }}>
              <select
                className="select"
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(Number(e.target.value))}
              >
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
                className="input"
                style={{ width: 120 }}
              />
              <button
                onClick={addCountLine}
                disabled={!selectedProductId || !actualQuantity}
                className="btn btn--primary btn--sm"
              >
                Add Item
              </button>
            </div>

            {selectedCount && selectedCount.lines && selectedCount.lines.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong>Items counted ({selectedCount.lines.length}):</strong>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Expected</th>
                      <th>Actual</th>
                      <th>Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCount.lines.map((line) => (
                      <tr key={line.id}>
                        <td>
                          {line.product_name || getProductName(line.product_id)}
                        </td>
                        <td>{line.expected_quantity}</td>
                        <td>{line.actual_quantity}</td>
                        <td className={line.variance !== 0 ? (line.variance > 0 ? "text-success" : "text-error") : ""}>
                          {line.variance > 0 ? "+" : ""}
                          {line.variance}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="form-actions" style={{ marginTop: 12 }}>
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
        <div className="form-row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h4>Counts ({counts.length})</h4>
          <label className="inline-toggle">
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
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {counts.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>{c.count_type}</td>
                  <td>
                    <span
                      className={`status-pill ${
                        c.status === "PENDING"
                          ? "status-pill--warning"
                          : c.status === "APPROVED"
                            ? "status-pill--success"
                            : c.status === "POSTED"
                              ? "status-pill--info"
                              : "status-pill--danger"
                      }`}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td>{c.reason || "-"}</td>
                  <td>
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="form-actions">
                      <button onClick={() => loadCountDetails(c.id)} className="btn btn--ghost btn--sm">
                        View
                      </button>
                      {c.status === "PENDING" && (
                        <>
                          <button
                            onClick={() => {
                              setActiveCountId(c.id);
                              loadCountDetails(c.id);
                            }}
                            className="btn btn--ghost btn--sm"
                          >
                            Add Items
                          </button>
                          <button onClick={() => performAction(c.id, "approve")} className="btn btn--primary btn--sm">
                            Approve
                          </button>
                          <button onClick={() => performAction(c.id, "cancel")} className="btn btn--warn btn--sm">
                            Cancel
                          </button>
                        </>
                      )}
                      {c.status === "APPROVED" && (
                        <button onClick={() => performAction(c.id, "post")} className="btn btn--primary btn--sm">
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
        <div className="overlay" onClick={() => setSelectedCount(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>Count #{selectedCount.id}</h3>
            <p><strong>Type:</strong> {selectedCount.count_type}</p>
            <p><strong>Status:</strong> {selectedCount.status}</p>
            <p><strong>Reason:</strong> {selectedCount.reason || "None"}</p>
            <p><strong>Created:</strong> {new Date(selectedCount.created_at).toLocaleString()}</p>

            {selectedCount.lines && selectedCount.lines.length > 0 && (
              <>
                <h4>Count Lines</h4>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Expected</th>
                      <th>Actual</th>
                      <th>Variance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCount.lines.map((line) => (
                      <tr key={line.id}>
                        <td>
                          {line.product_name || getProductName(line.product_id)}
                        </td>
                        <td>{line.expected_quantity}</td>
                        <td>{line.actual_quantity}</td>
                        <td
                          className={line.variance !== 0 ? (line.variance > 0 ? "text-success" : "text-error") : ""}
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

            <button onClick={() => setSelectedCount(null)} className="btn btn--ghost" style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
