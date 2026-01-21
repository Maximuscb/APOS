// Overview: React workflow component for returns workflow operations.

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

type SaleLine = {
  id: number;
  product_id: number;
  product_name?: string;
  sku?: string;
  quantity: number;
  unit_price_cents: number;
};

type Sale = {
  id: number;
  store_id: number;
  status: string;
  total_cents: number;
  created_at: string;
  lines: SaleLine[];
};

type Return = {
  id: number;
  original_sale_id: number;
  store_id: number;
  status: string;
  reason: string | null;
  created_at: string;
  lines?: ReturnLine[];
};

type ReturnLine = {
  id: number;
  original_sale_line_id: number;
  quantity: number;
  product_name?: string;
};

type Props = {
  storeId: number;
  isAuthed: boolean;
};

export function ReturnsWorkflow({ storeId, isAuthed }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // List of returns
  const [returns, setReturns] = useState<Return[]>([]);
  const [showPendingOnly, setShowPendingOnly] = useState(true);

  // Sale lookup
  const [saleIdInput, setSaleIdInput] = useState("");
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);

  // Return creation
  const [reason, setReason] = useState("");
  const [restockingFee, setRestockingFee] = useState("");
  const [lineQuantities, setLineQuantities] = useState<Record<number, number>>({});

  // Selected return for actions
  const [selectedReturn, setSelectedReturn] = useState<Return | null>(null);

  async function loadReturns() {
    if (!isAuthed) return;
    setLoading(true);
    try {
      const url = showPendingOnly
        ? `/api/returns/pending`
        : `/api/returns?store_id=${storeId}`;
      const result = await apiGet<{ returns: Return[] }>(url);
      setReturns(result.returns ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load returns");
    } finally {
      setLoading(false);
    }
  }

  async function lookupSale() {
    if (!saleIdInput.trim()) return;
    setError(null);
    setSelectedSale(null);
    try {
      const result = await apiGet<Sale>(`/api/sales/${saleIdInput}`);
      setSelectedSale(result);
      // Initialize quantities
      const qtys: Record<number, number> = {};
      result.lines?.forEach((line) => {
        qtys[line.id] = 0;
      });
      setLineQuantities(qtys);
    } catch (e: any) {
      setError(e?.message ?? "Sale not found");
    }
  }

  async function createReturn() {
    if (!selectedSale) return;
    setError(null);
    setNotice(null);

    // Check if any items selected
    const hasItems = Object.values(lineQuantities).some((q) => q > 0);
    if (!hasItems) {
      setError("Select at least one item to return");
      return;
    }

    try {
      // Create the return
      const returnResult = await apiPost<{ return: Return }>("/api/returns", {
        original_sale_id: selectedSale.id,
        store_id: storeId,
        reason: reason || undefined,
        restocking_fee_cents: restockingFee ? parseInt(restockingFee) : 0,
      });

      const returnId = returnResult.return.id;

      // Add lines for items with quantity > 0
      for (const line of selectedSale.lines ?? []) {
        const qty = lineQuantities[line.id];
        if (qty > 0) {
          await apiPost(`/api/returns/${returnId}/lines`, {
            original_sale_line_id: line.id,
            quantity: qty,
          });
        }
      }

      setNotice(`Return #${returnId} created successfully`);
      setSelectedSale(null);
      setSaleIdInput("");
      setReason("");
      setRestockingFee("");
      setLineQuantities({});
      loadReturns();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create return");
    }
  }

  async function loadReturnDetails(returnId: number) {
    try {
      const result = await apiGet<{ return: Return }>(`/api/returns/${returnId}`);
      setSelectedReturn(result.return);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load return details");
    }
  }

  async function performAction(returnId: number, action: string, data?: Record<string, any>) {
    setError(null);
    setNotice(null);
    try {
      await apiPost(`/api/returns/${returnId}/${action}`, data ?? {});
      setNotice(`Return ${action} successfully`);
      loadReturns();
      setSelectedReturn(null);
    } catch (e: any) {
      setError(e?.message ?? `Failed to ${action} return`);
    }
  }

  useEffect(() => {
    loadReturns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthed, showPendingOnly, storeId]);

  if (!isAuthed) {
    return <p className="muted">Sign in to manage returns.</p>;
  }

  return (
    <div>
      {error && <div className="alert">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}

      {/* Sale lookup section */}
      <div className="form-card" style={{ marginBottom: 16 }}>
        <h4>Create Return</h4>
        <div className="form-row" style={{ marginBottom: 8 }}>
          <label className="form-stack">
            <span className="form-label">Sale ID</span>
            <input
              className="input"
              value={saleIdInput}
              onChange={(e) => setSaleIdInput(e.target.value)}
              placeholder="Enter sale ID"
              style={{ width: 120 }}
            />
          </label>
          <button onClick={lookupSale} className="btn btn--primary btn--sm">
            Look Up Sale
          </button>
        </div>

        {selectedSale && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>Sale #{selectedSale.id}</strong> - {selectedSale.status} - $
              {(selectedSale.total_cents / 100).toFixed(2)}
            </p>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Qty Sold</th>
                  <th>Price</th>
                  <th>Return Qty</th>
                </tr>
              </thead>
              <tbody>
                {selectedSale.lines?.map((line) => (
                  <tr key={line.id}>
                    <td>
                      {line.product_name || line.sku || `Product #${line.product_id}`}
                    </td>
                    <td>{line.quantity}</td>
                    <td>
                      ${(line.unit_price_cents / 100).toFixed(2)}
                    </td>
                    <td>
                      <input
                        type="number"
                        min={0}
                        max={line.quantity}
                        value={lineQuantities[line.id] ?? 0}
                        onChange={(e) =>
                          setLineQuantities({
                            ...lineQuantities,
                            [line.id]: Math.min(line.quantity, Math.max(0, parseInt(e.target.value) || 0)),
                          })
                        }
                        className="input"
                        style={{ width: 90 }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="form-row" style={{ marginTop: 8 }}>
              <label className="form-stack">
                <span className="form-label">Reason</span>
                <input
                  className="input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Return reason"
                />
              </label>
              <label className="form-stack">
                <span className="form-label">Restocking Fee (cents)</span>
                <input
                  className="input"
                  value={restockingFee}
                  onChange={(e) => setRestockingFee(e.target.value)}
                  placeholder="0"
                  style={{ width: 100 }}
                />
              </label>
            </div>

            <div className="form-actions" style={{ marginTop: 12 }}>
              <button onClick={createReturn} className="btn btn--primary" style={{ marginRight: 8 }}>
                Create Return
              </button>
              <button onClick={() => setSelectedSale(null)} className="btn btn--ghost">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Returns list */}
      <div>
        <div className="form-row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h4>Returns ({returns.length})</h4>
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
        ) : returns.length === 0 ? (
          <p className="muted">No returns found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Sale ID</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.original_sale_id}</td>
                  <td>
                    <span
                      className={`status-pill ${
                        r.status === "PENDING"
                          ? "status-pill--warning"
                          : r.status === "APPROVED"
                            ? "status-pill--success"
                            : r.status === "COMPLETED"
                              ? "status-pill--info"
                              : "status-pill--danger"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td>{r.reason || "-"}</td>
                  <td>
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="form-actions">
                      <button onClick={() => loadReturnDetails(r.id)} className="btn btn--ghost btn--sm">
                        View
                      </button>
                      {r.status === "PENDING" && (
                        <>
                          <button
                            onClick={() => performAction(r.id, "approve")}
                            className="btn btn--primary btn--sm"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => performAction(r.id, "reject")}
                            className="btn btn--warn btn--sm"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {r.status === "APPROVED" && (
                        <button
                          onClick={() => performAction(r.id, "complete")}
                          className="btn btn--primary btn--sm"
                        >
                          Complete
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

      {/* Return details modal */}
      {selectedReturn && (
        <div className="overlay" onClick={() => setSelectedReturn(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>Return #{selectedReturn.id}</h3>
            <p>
              <strong>Status:</strong> {selectedReturn.status}
            </p>
            <p>
              <strong>Original Sale:</strong> #{selectedReturn.original_sale_id}
            </p>
            <p>
              <strong>Reason:</strong> {selectedReturn.reason || "None"}
            </p>
            <p>
              <strong>Created:</strong> {new Date(selectedReturn.created_at).toLocaleString()}
            </p>

            {selectedReturn.lines && selectedReturn.lines.length > 0 && (
              <>
                <h4>Lines</h4>
                <ul>
                  {selectedReturn.lines.map((line) => (
                    <li key={line.id}>
                      {line.product_name || `Line #${line.original_sale_line_id}`} x {line.quantity}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <button onClick={() => setSelectedReturn(null)} className="btn btn--ghost" style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
