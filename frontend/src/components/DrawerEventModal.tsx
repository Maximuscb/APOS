// Overview: Modal for cash drawer events (No Sale, Cash Drop) with manager approval.

import { useState } from "react";
import { apiPost } from "../lib/api";

type DrawerEventType = "NO_SALE" | "CASH_DROP";

type DrawerEventModalProps = {
  eventType: DrawerEventType;
  sessionId: number;
  hasManagerPermission: boolean;
  onClose: () => void;
  onEventLogged: () => void;
};

export function DrawerEventModal({
  eventType,
  sessionId,
  hasManagerPermission,
  onClose,
  onEventLogged,
}: DrawerEventModalProps) {
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNoSale = eventType === "NO_SALE";
  const isCashDrop = eventType === "CASH_DROP";

  async function handleSubmit() {
    if (!reason.trim()) {
      setError("Please provide a reason.");
      return;
    }

    if (isCashDrop) {
      const amount_cents = Math.round(Number(amount) * 100);
      if (!Number.isFinite(amount_cents) || amount_cents <= 0) {
        setError("Please enter a valid amount greater than $0.");
        return;
      }
    }

    // If user doesn't have manager permission, they need to enter manager PIN
    // For now, we'll rely on the backend to enforce this via the current user's permissions
    // The backend routes check for MANAGE_REGISTER permission

    setLoading(true);
    setError(null);

    try {
      if (isNoSale) {
        await apiPost(`/api/registers/sessions/${sessionId}/drawer/no-sale`, {
          reason: reason.trim(),
        });
      } else {
        const amount_cents = Math.round(Number(amount) * 100);
        await apiPost(`/api/registers/sessions/${sessionId}/drawer/cash-drop`, {
          amount_cents,
          reason: reason.trim(),
        });
      }
      onEventLogged();
    } catch (e: any) {
      setError(e?.message ?? `Failed to log ${isNoSale ? "no-sale" : "cash drop"} event.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal__header">
          <h2>{isNoSale ? "Open Drawer (No Sale)" : "Cash Drop"}</h2>
          <p className="muted">
            {isNoSale
              ? "Open the cash drawer without processing a sale."
              : "Remove excess cash from the drawer for safekeeping."}
          </p>
        </div>
        <div className="modal__body">
          {error && <div className="alert">{error}</div>}

          {!hasManagerPermission && (
            <div className="alert alert--info">
              Manager approval required. Please have a manager perform this action.
            </div>
          )}

          {isCashDrop && (
            <label className="field">
              <span>Amount to Remove (USD)</span>
              <input
                className="input"
                type="text"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                autoFocus={isCashDrop}
              />
            </label>
          )}

          <label className="field">
            <span>Reason</span>
            <input
              className="input"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={isNoSale ? "e.g., Customer needed change" : "e.g., Safe drop - drawer over $200"}
              autoFocus={isNoSale}
            />
          </label>
        </div>
        <div className="modal__actions">
          <button
            className="btn btn--primary"
            type="button"
            onClick={handleSubmit}
            disabled={loading || !reason.trim() || (isCashDrop && !amount) || !hasManagerPermission}
          >
            {loading ? "Processing..." : isNoSale ? "Open Drawer" : "Log Cash Drop"}
          </button>
          <button className="btn btn--ghost" type="button" onClick={onClose} disabled={loading}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
