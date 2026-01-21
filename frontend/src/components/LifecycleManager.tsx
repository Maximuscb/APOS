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
    <div className="form-card" style={{ marginTop: 20 }}>
      <h3 className="form-title" style={{ marginBottom: 12 }}>
        Lifecycle Management (Approve/Post)
      </h3>

      {error && (
        <div className="notice notice--error" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          {draftTxs.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 className="form-title" style={{ margin: "0 0 8px", fontSize: 13 }}>
                Pending Approval ({draftTxs.length})
              </h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Qty Delta</th>
                    <th>Note</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {draftTxs.map((tx) => (
                    <tr key={tx.id}>
                      <td>{tx.id}</td>
                      <td>{tx.type}</td>
                      <td>{tx.quantity_delta}</td>
                      <td>{tx.note ?? "-"}</td>
                      <td>
                        <button
                          onClick={() => approveTransaction(tx.id)}
                          className="btn btn--ghost btn--sm"
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
              <h4 className="form-title" style={{ margin: "0 0 8px", fontSize: 13 }}>
                Ready to Post ({approvedTxs.length})
              </h4>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Qty Delta</th>
                    <th>Note</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {approvedTxs.map((tx) => (
                    <tr key={tx.id}>
                      <td>{tx.id}</td>
                      <td>{tx.type}</td>
                      <td>{tx.quantity_delta}</td>
                      <td>{tx.note ?? "-"}</td>
                      <td>
                        <button
                          onClick={() => postTransaction(tx.id)}
                          className="btn btn--primary btn--sm"
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
            <div className="helper-text">No pending transactions</div>
          )}
        </>
      )}
    </div>
  );
}
