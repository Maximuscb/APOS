// Overview: Modal for closing a register shift with cash count.

import { useState } from "react";
import { apiPost } from "../lib/api";

type EndShiftModalProps = {
  sessionId: number;
  registerNumber: string;
  onClose: () => void;
  onShiftEnded: () => void;
};

type CloseResult = {
  session: {
    id: number;
    closing_cash_cents: number;
    expected_cash_cents: number | null;
    variance_cents: number | null;
  };
};

export function EndShiftModal({
  sessionId,
  registerNumber,
  onClose,
  onShiftEnded,
}: EndShiftModalProps) {
  const [closingCash, setClosingCash] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CloseResult | null>(null);

  async function handleCloseShift() {
    const closing_cash_cents = Math.round(Number(closingCash) * 100);
    if (!Number.isFinite(closing_cash_cents) || closing_cash_cents < 0) {
      setError("Please enter a valid closing cash amount.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<CloseResult>(`/api/registers/sessions/${sessionId}/close`, {
        closing_cash_cents,
        notes: notes || null,
      });
      setResult(res);
    } catch (e: any) {
      setError(e?.message ?? "Failed to close shift.");
    } finally {
      setLoading(false);
    }
  }

  function formatCents(cents: number | null | undefined): string {
    if (cents == null) return "--";
    return `$${(cents / 100).toFixed(2)}`;
  }

  function getVarianceClass(variance: number | null | undefined): string {
    if (variance == null) return "";
    if (variance < 0) return "text-error";
    if (variance > 0) return "text-success";
    return "";
  }

  if (result) {
    const variance = result.session.variance_cents;
    return (
      <div className="modal-overlay">
        <div className="modal">
          <div className="modal__header">
            <h2>Shift Closed</h2>
          </div>
          <div className="modal__body">
            <div className="shift-summary">
              <div className="shift-summary__row">
                <span>Register</span>
                <span>{registerNumber}</span>
              </div>
              <div className="shift-summary__row">
                <span>Closing Cash</span>
                <span>{formatCents(result.session.closing_cash_cents)}</span>
              </div>
              <div className="shift-summary__row">
                <span>Expected Cash</span>
                <span>{formatCents(result.session.expected_cash_cents)}</span>
              </div>
              <div className={`shift-summary__row shift-summary__row--variance ${getVarianceClass(variance)}`}>
                <span>Variance</span>
                <span>
                  {variance != null
                    ? variance >= 0
                      ? `+${formatCents(variance)} (over)`
                      : `${formatCents(variance)} (short)`
                    : "--"}
                </span>
              </div>
            </div>
          </div>
          <div className="modal__actions">
            <button className="btn btn--primary" type="button" onClick={onShiftEnded}>
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal__header">
          <h2>End Shift</h2>
          <p className="muted">Count the cash drawer and close the shift on {registerNumber}.</p>
        </div>
        <div className="modal__body">
          {error && <div className="alert">{error}</div>}

          <label className="field">
            <span>Closing Cash (USD)</span>
            <input
              className="input"
              type="text"
              inputMode="decimal"
              value={closingCash}
              onChange={(e) => setClosingCash(e.target.value)}
              placeholder="0.00"
              autoFocus
            />
          </label>

          <label className="field">
            <span>Notes (optional)</span>
            <textarea
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any notes about this shift..."
              rows={3}
            />
          </label>
        </div>
        <div className="modal__actions">
          <button
            className="btn btn--primary"
            type="button"
            onClick={handleCloseShift}
            disabled={loading || !closingCash}
          >
            {loading ? "Closing..." : "Close Shift"}
          </button>
          <button className="btn btn--ghost" type="button" onClick={onClose} disabled={loading}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
