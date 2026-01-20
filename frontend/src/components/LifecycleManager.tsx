// Overview: React component for lifecycle manager UI.

// frontend/src/components/LifecycleManager.tsx
import { useState, useEffect } from "react";
import { apiGet, apiPost } from "../lib/api";

type Transaction = {
  id: number;
  type: string;
  status: string;
  quantity_delta: number;
  product_id: number;
  note: string | null;
  occurred_at: string;
};

export function LifecycleManager({
  refreshToken,
  storeId,
}: {
  refreshToken: number;
  storeId: number;
}) {
  const [draftTxs, setDraftTxs] = useState<Transaction[]>([]);
  const [approvedTxs, setApprovedTxs] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadTransactions() {
    setLoading(true);
    setError(null);
    try {
      const drafts = await apiGet<{ transactions: Transaction[] }>(
        `/api/lifecycle/pending?store_id=${storeId}`
      );
      const approved = await apiGet<{ transactions: Transaction[] }>(
        `/api/lifecycle/approved?store_id=${storeId}`
      );
      setDraftTxs(drafts.transactions);
      setApprovedTxs(approved.transactions);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function approveTransaction(id: number) {
    try {
      await apiPost(`/api/lifecycle/approve/${id}`, {});
      await loadTransactions();
      alert(`Transaction ${id} approved!`);
    } catch (e: any) {
      setError(e?.message ?? "Failed to approve");
    }
  }

  async function postTransaction(id: number) {
    try {
      await apiPost(`/api/lifecycle/post/${id}`, {});
      await loadTransactions();
      alert(`Transaction ${id} posted!`);
    } catch (e: any) {
      setError(e?.message ?? "Failed to post");
    }
  }

  useEffect(() => {
    loadTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken, storeId]);

  return (
    <div style={{ marginTop: 20, padding: 12, border: "1px solid #ddd" }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
        Lifecycle Management (Approve/Post)
      </h3>

      {error && (
        <div style={{ padding: 8, background: "#fff5f5", color: "#9b1c1c", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          {draftTxs.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600 }}>
                Pending Approval ({draftTxs.length})
              </h4>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ddd" }}>
                    <th style={{ textAlign: "left", padding: 4 }}>ID</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Type</th>
                    <th style={{ textAlign: "right", padding: 4 }}>Qty Δ</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Note</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {draftTxs.map((tx) => (
                    <tr key={tx.id} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ padding: 4 }}>{tx.id}</td>
                      <td style={{ padding: 4 }}>{tx.type}</td>
                      <td style={{ textAlign: "right", padding: 4 }}>{tx.quantity_delta}</td>
                      <td style={{ padding: 4 }}>{tx.note ?? "—"}</td>
                      <td style={{ padding: 4 }}>
                        <button
                          onClick={() => approveTransaction(tx.id)}
                          style={{ padding: "4px 8px", fontSize: 11 }}
                        >
                          Approve
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {approvedTxs.length > 0 && (
            <div>
              <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600 }}>
                Ready to Post ({approvedTxs.length})
              </h4>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #ddd" }}>
                    <th style={{ textAlign: "left", padding: 4 }}>ID</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Type</th>
                    <th style={{ textAlign: "right", padding: 4 }}>Qty Δ</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Note</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {approvedTxs.map((tx) => (
                    <tr key={tx.id} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ padding: 4 }}>{tx.id}</td>
                      <td style={{ padding: 4 }}>{tx.type}</td>
                      <td style={{ textAlign: "right", padding: 4 }}>{tx.quantity_delta}</td>
                      <td style={{ padding: 4 }}>{tx.note ?? "—"}</td>
                      <td style={{ padding: 4 }}>
                        <button
                          onClick={() => postTransaction(tx.id)}
                          style={{
                            padding: "4px 8px",
                            fontSize: 11,
                            background: "#10b981",
                            color: "white",
                            border: "none",
                          }}
                        >
                          Post
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {draftTxs.length === 0 && approvedTxs.length === 0 && (
            <div style={{ color: "#666", fontSize: 13 }}>No pending transactions</div>
          )}
        </>
      )}
    </div>
  );
}
