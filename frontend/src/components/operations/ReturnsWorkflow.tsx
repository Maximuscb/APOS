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
      <div style={{ marginBottom: 16, padding: 12, border: "1px solid #ddd", background: "#f9f9f9" }}>
        <h4>Create Return</h4>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 8 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span>Sale ID</span>
            <input
              value={saleIdInput}
              onChange={(e) => setSaleIdInput(e.target.value)}
              placeholder="Enter sale ID"
              style={{ width: 120 }}
            />
          </label>
          <button onClick={lookupSale} style={{ padding: "6px 12px" }}>
            Look Up Sale
          </button>
        </div>

        {selectedSale && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>Sale #{selectedSale.id}</strong> - {selectedSale.status} - $
              {(selectedSale.total_cents / 100).toFixed(2)}
            </p>

            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Product</th>
                  <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Qty Sold</th>
                  <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Price</th>
                  <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid #ddd" }}>Return Qty</th>
                </tr>
              </thead>
              <tbody>
                {selectedSale.lines?.map((line) => (
                  <tr key={line.id}>
                    <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>
                      {line.product_name || line.sku || `Product #${line.product_id}`}
                    </td>
                    <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>{line.quantity}</td>
                    <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>
                      ${(line.unit_price_cents / 100).toFixed(2)}
                    </td>
                    <td style={{ padding: 4, borderBottom: "1px solid #eee" }}>
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
                        style={{ width: 60 }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span>Reason</span>
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Return reason"
                />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span>Restocking Fee (cents)</span>
                <input
                  value={restockingFee}
                  onChange={(e) => setRestockingFee(e.target.value)}
                  placeholder="0"
                  style={{ width: 100 }}
                />
              </label>
            </div>

            <div style={{ marginTop: 12 }}>
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h4>Returns ({returns.length})</h4>
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
        ) : returns.length === 0 ? (
          <p className="muted">No returns found.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>ID</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Sale ID</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Status</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Reason</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Created</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #ddd" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{r.id}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{r.original_sale_id}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: 4,
                        fontSize: 12,
                        background:
                          r.status === "PENDING"
                            ? "#fff3cd"
                            : r.status === "APPROVED"
                              ? "#d4edda"
                              : r.status === "COMPLETED"
                                ? "#cce5ff"
                                : "#f8d7da",
                      }}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>{r.reason || "-"}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      <button onClick={() => loadReturnDetails(r.id)} style={{ padding: "2px 6px", fontSize: 12 }}>
                        View
                      </button>
                      {r.status === "PENDING" && (
                        <>
                          <button
                            onClick={() => performAction(r.id, "approve")}
                            style={{ padding: "2px 6px", fontSize: 12 }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => performAction(r.id, "reject")}
                            style={{ padding: "2px 6px", fontSize: 12 }}
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {r.status === "APPROVED" && (
                        <button
                          onClick={() => performAction(r.id, "complete")}
                          style={{ padding: "2px 6px", fontSize: 12 }}
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
          onClick={() => setSelectedReturn(null)}
        >
          <div
            style={{
              background: "white",
              padding: 24,
              borderRadius: 8,
              maxWidth: 500,
              width: "90%",
            }}
            onClick={(e) => e.stopPropagation()}
          >
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

            <button onClick={() => setSelectedReturn(null)} style={{ marginTop: 16 }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
