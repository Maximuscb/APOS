import { useState } from "react";
import { apiPost } from "../lib/api";

type Props = {
  storeId: number;
  isAuthed: boolean;
};

export function OperationsPanel({ storeId, isAuthed }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [returnForm, setReturnForm] = useState({
    original_sale_id: "",
    reason: "",
    restocking_fee_cents: "",
  });
  const [returnLineForm, setReturnLineForm] = useState({
    return_id: "",
    original_sale_line_id: "",
    quantity: "",
  });
  const [returnAction, setReturnAction] = useState({
    return_id: "",
    rejection_reason: "",
  });

  const [transferForm, setTransferForm] = useState({
    from_store_id: String(storeId),
    to_store_id: "",
    reason: "",
  });
  const [transferLineForm, setTransferLineForm] = useState({
    transfer_id: "",
    product_id: "",
    quantity: "",
  });
  const [transferAction, setTransferAction] = useState({
    transfer_id: "",
    reason: "",
  });

  const [countForm, setCountForm] = useState({
    count_type: "CYCLE",
    reason: "",
  });
  const [countLineForm, setCountLineForm] = useState({
    count_id: "",
    product_id: "",
    actual_quantity: "",
  });
  const [countAction, setCountAction] = useState({
    count_id: "",
    reason: "",
  });

  async function handleRequest<T>(fn: () => Promise<T>, successMessage: string) {
    if (!isAuthed) {
      setError("Login required to perform operations.");
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(successMessage);
    } catch (e: any) {
      setError(e?.message ?? "Request failed");
    }
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Operational Documents</h2>
          <p className="muted">Create and action returns, transfers, and counts without raw API calls.</p>
        </div>
      </div>

      {!isAuthed && <div className="alert">Login required to manage operational documents.</div>}
      {error && <div className="alert">{error}</div>}
      {notice && <div className="alert alert--success">{notice}</div>}

      <div className="panel__grid">
        <div className="panel__section">
          <h3>Returns</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Original sale ID"
              value={returnForm.original_sale_id}
              onChange={(e) => setReturnForm({ ...returnForm, original_sale_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Reason"
              value={returnForm.reason}
              onChange={(e) => setReturnForm({ ...returnForm, reason: e.target.value })}
            />
            <input
              className="input"
              placeholder="Restocking fee (cents)"
              value={returnForm.restocking_fee_cents}
              onChange={(e) => setReturnForm({ ...returnForm, restocking_fee_cents: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost("/api/returns", {
                      original_sale_id: Number(returnForm.original_sale_id),
                      store_id: storeId,
                      reason: returnForm.reason || undefined,
                      restocking_fee_cents: returnForm.restocking_fee_cents
                        ? Number(returnForm.restocking_fee_cents)
                        : 0,
                    }),
                  "Return created."
                )
              }
            >
              Create return
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Return ID"
              value={returnLineForm.return_id}
              onChange={(e) => setReturnLineForm({ ...returnLineForm, return_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Sale line ID"
              value={returnLineForm.original_sale_line_id}
              onChange={(e) => setReturnLineForm({ ...returnLineForm, original_sale_line_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Quantity"
              value={returnLineForm.quantity}
              onChange={(e) => setReturnLineForm({ ...returnLineForm, quantity: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/returns/${returnLineForm.return_id}/lines`, {
                      original_sale_line_id: Number(returnLineForm.original_sale_line_id),
                      quantity: Number(returnLineForm.quantity),
                    }),
                  "Return line added."
                )
              }
            >
              Add return line
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Return ID"
              value={returnAction.return_id}
              onChange={(e) => setReturnAction({ ...returnAction, return_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Rejection reason (optional)"
              value={returnAction.rejection_reason}
              onChange={(e) => setReturnAction({ ...returnAction, rejection_reason: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/returns/${returnAction.return_id}/approve`, {}),
                  "Return approved."
                )
              }
            >
              Approve
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/returns/${returnAction.return_id}/reject`, {
                      rejection_reason: returnAction.rejection_reason,
                    }),
                  "Return rejected."
                )
              }
            >
              Reject
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/returns/${returnAction.return_id}/complete`, {}),
                  "Return completed."
                )
              }
            >
              Complete
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Transfers</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="From store ID"
              value={transferForm.from_store_id}
              onChange={(e) => setTransferForm({ ...transferForm, from_store_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="To store ID"
              value={transferForm.to_store_id}
              onChange={(e) => setTransferForm({ ...transferForm, to_store_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Reason"
              value={transferForm.reason}
              onChange={(e) => setTransferForm({ ...transferForm, reason: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost("/api/transfers", {
                      from_store_id: Number(transferForm.from_store_id),
                      to_store_id: Number(transferForm.to_store_id),
                      reason: transferForm.reason || undefined,
                    }),
                  "Transfer created."
                )
              }
            >
              Create transfer
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Transfer ID"
              value={transferLineForm.transfer_id}
              onChange={(e) => setTransferLineForm({ ...transferLineForm, transfer_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Product ID"
              value={transferLineForm.product_id}
              onChange={(e) => setTransferLineForm({ ...transferLineForm, product_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Quantity"
              value={transferLineForm.quantity}
              onChange={(e) => setTransferLineForm({ ...transferLineForm, quantity: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/transfers/${transferLineForm.transfer_id}/lines`, {
                      product_id: Number(transferLineForm.product_id),
                      quantity: Number(transferLineForm.quantity),
                    }),
                  "Transfer line added."
                )
              }
            >
              Add transfer line
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Transfer ID"
              value={transferAction.transfer_id}
              onChange={(e) => setTransferAction({ ...transferAction, transfer_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Cancel reason (optional)"
              value={transferAction.reason}
              onChange={(e) => setTransferAction({ ...transferAction, reason: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/transfers/${transferAction.transfer_id}/approve`, {}),
                  "Transfer approved."
                )
              }
            >
              Approve
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/transfers/${transferAction.transfer_id}/ship`, {}),
                  "Transfer shipped."
                )
              }
            >
              Ship
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/transfers/${transferAction.transfer_id}/receive`, {}),
                  "Transfer received."
                )
              }
            >
              Receive
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/transfers/${transferAction.transfer_id}/cancel`, {
                      reason: transferAction.reason,
                    }),
                  "Transfer cancelled."
                )
              }
            >
              Cancel
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Counts</h3>
          <div className="form-grid">
            <select
              className="input"
              value={countForm.count_type}
              onChange={(e) => setCountForm({ ...countForm, count_type: e.target.value })}
            >
              <option value="CYCLE">CYCLE</option>
              <option value="FULL">FULL</option>
            </select>
            <input
              className="input"
              placeholder="Reason"
              value={countForm.reason}
              onChange={(e) => setCountForm({ ...countForm, reason: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost("/api/counts", {
                      store_id: storeId,
                      count_type: countForm.count_type,
                      reason: countForm.reason || undefined,
                    }),
                  "Count created."
                )
              }
            >
              Create count
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Count ID"
              value={countLineForm.count_id}
              onChange={(e) => setCountLineForm({ ...countLineForm, count_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Product ID"
              value={countLineForm.product_id}
              onChange={(e) => setCountLineForm({ ...countLineForm, product_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Actual quantity"
              value={countLineForm.actual_quantity}
              onChange={(e) => setCountLineForm({ ...countLineForm, actual_quantity: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/counts/${countLineForm.count_id}/lines`, {
                      product_id: Number(countLineForm.product_id),
                      actual_quantity: Number(countLineForm.actual_quantity),
                    }),
                  "Count line added."
                )
              }
            >
              Add count line
            </button>
          </div>

          <div className="form-grid">
            <input
              className="input"
              placeholder="Count ID"
              value={countAction.count_id}
              onChange={(e) => setCountAction({ ...countAction, count_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Cancel reason (optional)"
              value={countAction.reason}
              onChange={(e) => setCountAction({ ...countAction, reason: e.target.value })}
            />
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/counts/${countAction.count_id}/approve`, {}),
                  "Count approved."
                )
              }
            >
              Approve
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () => apiPost(`/api/counts/${countAction.count_id}/post`, {}),
                  "Count posted."
                )
              }
            >
              Post
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() =>
                handleRequest(
                  () =>
                    apiPost(`/api/counts/${countAction.count_id}/cancel`, {
                      reason: countAction.reason,
                    }),
                  "Count cancelled."
                )
              }
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
