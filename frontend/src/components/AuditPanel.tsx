import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

type PaymentTransaction = {
  id: number;
  sale_id: number;
  transaction_type: string;
  amount_cents: number;
  occurred_at: string;
};

type DrawerEvent = {
  id: number;
  register_id: number;
  register_session_id: number;
  event_type: string;
  amount_cents: number | null;
  occurred_at: string;
};

export function AuditPanel({ authVersion }: { authVersion: number }) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [paymentFilters, setPaymentFilters] = useState({
    sale_id: "",
    transaction_type: "",
    start_date: "",
    end_date: "",
    limit: 50,
  });
  const [paymentTransactions, setPaymentTransactions] = useState<PaymentTransaction[]>([]);

  const [drawerFilters, setDrawerFilters] = useState({
    register_id: "",
    event_type: "",
    start_date: "",
    end_date: "",
    limit: 50,
  });
  const [drawerEvents, setDrawerEvents] = useState<DrawerEvent[]>([]);

  async function loadPaymentTransactions() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (paymentFilters.sale_id) params.append("sale_id", paymentFilters.sale_id);
      if (paymentFilters.transaction_type) params.append("transaction_type", paymentFilters.transaction_type);
      if (paymentFilters.start_date) params.append("start_date", paymentFilters.start_date);
      if (paymentFilters.end_date) params.append("end_date", paymentFilters.end_date);
      params.append("limit", String(paymentFilters.limit));

      const result = await apiGet<{ transactions: PaymentTransaction[] }>(
        `/api/payments/transactions?${params.toString()}`
      );
      setPaymentTransactions(result.transactions ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load payment transactions");
    } finally {
      setLoading(false);
    }
  }

  async function loadDrawerEvents() {
    if (!drawerFilters.register_id) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (drawerFilters.event_type) params.append("event_type", drawerFilters.event_type);
      if (drawerFilters.start_date) params.append("start_date", drawerFilters.start_date);
      if (drawerFilters.end_date) params.append("end_date", drawerFilters.end_date);
      params.append("limit", String(drawerFilters.limit));

      const result = await apiGet<{ events: DrawerEvent[] }>(
        `/api/registers/${drawerFilters.register_id}/events?${params.toString()}`
      );
      setDrawerEvents(result.events ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load drawer events");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPaymentTransactions([]);
    setDrawerEvents([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authVersion]);

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Audit Logs</h2>
          <p className="muted">Review payment transactions and register drawer activity.</p>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <div className="panel__grid">
        <div className="panel__section">
          <h3>Payment Transactions</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Sale ID"
              value={paymentFilters.sale_id}
              onChange={(e) => setPaymentFilters({ ...paymentFilters, sale_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Transaction type"
              value={paymentFilters.transaction_type}
              onChange={(e) => setPaymentFilters({ ...paymentFilters, transaction_type: e.target.value })}
            />
            <input
              className="input"
              placeholder="Start date (ISO)"
              value={paymentFilters.start_date}
              onChange={(e) => setPaymentFilters({ ...paymentFilters, start_date: e.target.value })}
            />
            <input
              className="input"
              placeholder="End date (ISO)"
              value={paymentFilters.end_date}
              onChange={(e) => setPaymentFilters({ ...paymentFilters, end_date: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Limit"
              value={paymentFilters.limit}
              onChange={(e) => setPaymentFilters({ ...paymentFilters, limit: Number(e.target.value) })}
            />
            <button className="btn btn--ghost" type="button" onClick={loadPaymentTransactions} disabled={loading}>
              Load payments audit
            </button>
          </div>
          {paymentTransactions.length > 0 && (
            <div className="data-block">
              {paymentTransactions.map((tx) => (
                <div key={tx.id} className="data-row">
                  <span>
                    {tx.transaction_type} - Sale {tx.sale_id}
                  </span>
                  <span>${(tx.amount_cents / 100).toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel__section">
          <h3>Drawer Events</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Register ID"
              value={drawerFilters.register_id}
              onChange={(e) => setDrawerFilters({ ...drawerFilters, register_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Event type"
              value={drawerFilters.event_type}
              onChange={(e) => setDrawerFilters({ ...drawerFilters, event_type: e.target.value })}
            />
            <input
              className="input"
              placeholder="Start date (ISO)"
              value={drawerFilters.start_date}
              onChange={(e) => setDrawerFilters({ ...drawerFilters, start_date: e.target.value })}
            />
            <input
              className="input"
              placeholder="End date (ISO)"
              value={drawerFilters.end_date}
              onChange={(e) => setDrawerFilters({ ...drawerFilters, end_date: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Limit"
              value={drawerFilters.limit}
              onChange={(e) => setDrawerFilters({ ...drawerFilters, limit: Number(e.target.value) })}
            />
            <button className="btn btn--ghost" type="button" onClick={loadDrawerEvents} disabled={loading}>
              Load drawer events
            </button>
          </div>
          {drawerEvents.length > 0 && (
            <div className="data-block">
              {drawerEvents.map((event) => (
                <div key={event.id} className="data-row">
                  <span>
                    {event.event_type} - Register {event.register_id}
                  </span>
                  <span>
                    {event.amount_cents ? `$${(event.amount_cents / 100).toFixed(2)}` : "n/a"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
