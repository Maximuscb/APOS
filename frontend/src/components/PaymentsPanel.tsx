// Overview: React component for payments panel UI.

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

type Payment = {
  id: number;
  sale_id: number;
  tender_type: string;
  amount_cents: number;
  status: string;
};

type PaymentSummary = {
  total_due_cents: number;
  total_paid_cents: number;
  remaining_cents: number;
  change_due_cents: number;
  payment_status: string;
};

export function PaymentsPanel({
  authVersion,
  isAuthed,
  registerId,
  sessionId,
}: {
  authVersion: number;
  isAuthed: boolean;
  registerId?: number | null;
  sessionId?: number | null;
}) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saleId, setSaleId] = useState("");
  const [includeVoided, setIncludeVoided] = useState(false);
  const [salePayments, setSalePayments] = useState<Payment[]>([]);
  const [saleSummary, setSaleSummary] = useState<PaymentSummary | null>(null);

  const [paymentForm, setPaymentForm] = useState({
    sale_id: "",
    tender_type: "CASH",
    amount_cents: 0,
    reference_number: "",
  });

  const [voidForm, setVoidForm] = useState({
    payment_id: "",
    reason: "",
  });

  const [tenderSummary, setTenderSummary] = useState<Record<string, number> | null>(null);
  const [tenderSessionId, setTenderSessionId] = useState("");

  async function addPayment() {
    if (!isAuthed) {
      setError("Login required to add payments.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/payments/", {
        sale_id: Number(paymentForm.sale_id),
        tender_type: paymentForm.tender_type,
        amount_cents: Number(paymentForm.amount_cents),
        reference_number: paymentForm.reference_number || null,
        register_id: registerId ?? null,
        register_session_id: sessionId ?? null,
      });
      setPaymentForm({
        sale_id: "",
        tender_type: "CASH",
        amount_cents: 0,
        reference_number: "",
      });
    } catch (e: any) {
      setError(e?.message ?? "Failed to add payment");
    } finally {
      setLoading(false);
    }
  }

  async function loadSalePayments() {
    if (!saleId) return;
    if (!isAuthed) {
      setError("Login required to view payments.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ payments: Payment[]; summary: PaymentSummary }>(
        `/api/payments/sales/${saleId}?include_voided=${includeVoided ? "true" : "false"}`
      );
      setSalePayments(result.payments ?? []);
      setSaleSummary(result.summary ?? null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load payments");
    } finally {
      setLoading(false);
    }
  }

  async function voidPayment() {
    if (!voidForm.payment_id) return;
    if (!isAuthed) {
      setError("Login required to void payments.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/payments/${voidForm.payment_id}/void`, {
        reason: voidForm.reason,
        register_id: registerId ?? null,
        register_session_id: sessionId ?? null,
      });
      setVoidForm({ payment_id: "", reason: "" });
    } catch (e: any) {
      setError(e?.message ?? "Failed to void payment");
    } finally {
      setLoading(false);
    }
  }

  async function loadTenderSummary() {
    if (!tenderSessionId) return;
    if (!isAuthed) {
      setError("Login required to view tender summaries.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ tender_totals_cents: Record<string, number> }>(
        `/api/payments/sessions/${tenderSessionId}/tender-summary`
      );
      setTenderSummary(result.tender_totals_cents ?? null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load tender summary");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSalePayments([]);
    setSaleSummary(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authVersion]);

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Payments</h2>
          <p className="muted">Add tenders, review summaries, and void payments when needed.</p>
        </div>
      </div>

      {!isAuthed && <div className="alert">Login required for payment operations.</div>}
      {error && <div className="alert">{error}</div>}

      <div className="panel__grid">
        <div className="panel__section">
          <h3>Add Payment</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Sale ID"
              value={paymentForm.sale_id}
              onChange={(e) => setPaymentForm({ ...paymentForm, sale_id: e.target.value })}
            />
            <select
              className="input"
              value={paymentForm.tender_type}
              onChange={(e) => setPaymentForm({ ...paymentForm, tender_type: e.target.value })}
            >
              <option value="CASH">CASH</option>
              <option value="CARD">CARD</option>
              <option value="CHECK">CHECK</option>
              <option value="GIFT_CARD">GIFT_CARD</option>
              <option value="STORE_CREDIT">STORE_CREDIT</option>
            </select>
            <input
              className="input"
              type="number"
              placeholder="Amount (cents)"
              value={paymentForm.amount_cents}
              onChange={(e) => setPaymentForm({ ...paymentForm, amount_cents: Number(e.target.value) })}
            />
            <input
              className="input"
              placeholder="Reference number"
              value={paymentForm.reference_number}
              onChange={(e) => setPaymentForm({ ...paymentForm, reference_number: e.target.value })}
            />
            {(registerId || sessionId) && (
              <div className="muted">
                Register: {registerId ?? "N/A"} | Session: {sessionId ?? "N/A"}
              </div>
            )}
            <button className="btn btn--primary" type="button" onClick={addPayment} disabled={loading}>
              Add payment
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Sale Payments</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Sale ID"
              value={saleId}
              onChange={(e) => setSaleId(e.target.value)}
            />
            <label className="inline-toggle">
              <input
                type="checkbox"
                checked={includeVoided}
                onChange={(e) => setIncludeVoided(e.target.checked)}
              />
              Include voided
            </label>
            <button className="btn btn--ghost" type="button" onClick={loadSalePayments} disabled={loading}>
              Load payments
            </button>
            {saleSummary && (
              <div className="data-block">
                <div className="data-row">
                  <span>Status</span>
                  <span>{saleSummary.payment_status}</span>
                </div>
                <div className="data-row">
                  <span>Remaining</span>
                  <span>${(saleSummary.remaining_cents / 100).toFixed(2)}</span>
                </div>
                <div className="data-row">
                  <span>Change due</span>
                  <span>${(saleSummary.change_due_cents / 100).toFixed(2)}</span>
                </div>
              </div>
            )}
            {salePayments.length > 0 && (
              <div className="data-block">
                {salePayments.map((payment) => (
                  <div key={payment.id} className="data-row">
                    <span>
                      {payment.tender_type} - #{payment.id}
                    </span>
                    <span>${(payment.amount_cents / 100).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel__section">
          <h3>Void Payment</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Payment ID"
              value={voidForm.payment_id}
              onChange={(e) => setVoidForm({ ...voidForm, payment_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Reason"
              value={voidForm.reason}
              onChange={(e) => setVoidForm({ ...voidForm, reason: e.target.value })}
            />
            <button className="btn btn--ghost" type="button" onClick={voidPayment} disabled={loading}>
              Void payment
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Tender Summary</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Register session ID"
              value={tenderSessionId}
              onChange={(e) => setTenderSessionId(e.target.value)}
            />
            <button className="btn btn--ghost" type="button" onClick={loadTenderSummary} disabled={loading}>
              Load tender totals
            </button>
            {tenderSummary && (
              <div className="data-block">
                {Object.entries(tenderSummary).map(([key, value]) => (
                  <div key={key} className="data-row">
                    <span>{key}</span>
                    <span>${(value / 100).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
