import { useState } from 'react';
import { api } from '@/lib/api';
import { formatMoney, formatDateTime } from '@/lib/format';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AuditsPage() {
  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Events</h1>
        <p className="text-sm text-muted mt-1">
          Review payment transactions and cash drawer events.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PaymentTransactionsSection />
        <DrawerEventsSection />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Payment Transactions                                               */
/* ------------------------------------------------------------------ */

function PaymentTransactionsSection() {
  const [saleId, setSaleId] = useState('');
  const [transactionType, setTransactionType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState('50');
  const [transactions, setTransactions] = useState<PaymentTransaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadTransactions() {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (saleId.trim()) params.set('sale_id', saleId.trim());
      if (transactionType.trim()) params.set('transaction_type', transactionType.trim());
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      if (limit.trim()) params.set('limit', limit.trim());

      const res = await api.get<{ transactions: PaymentTransaction[] }>(
        `/api/payments/transactions?${params}`,
      );
      setTransactions(res.transactions ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load transactions.');
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardTitle>Payment Transactions</CardTitle>

      {error && (
        <div className="mt-3 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
        <Input
          label="Sale ID"
          value={saleId}
          onChange={(e) => setSaleId(e.target.value)}
          placeholder="Filter by sale"
        />
        <Input
          label="Transaction Type"
          value={transactionType}
          onChange={(e) => setTransactionType(e.target.value)}
          placeholder="e.g. PAYMENT, REFUND"
        />
        <Input
          label="Start Date"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <Input
          label="End Date"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <Input
          label="Limit"
          type="number"
          min="1"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
        />
      </div>

      <div className="mt-4">
        <Button onClick={loadTransactions} disabled={loading}>
          {loading ? 'Loading...' : 'Load Transactions'}
        </Button>
      </div>

      {/* Results */}
      {transactions.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">Sale</th>
                <th className="py-2 pr-3 font-medium">Type</th>
                <th className="py-2 pr-3 font-medium text-right">Amount</th>
                <th className="py-2 font-medium">Occurred At</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id} className="border-b border-border/50">
                  <td className="py-2 pr-3 tabular-nums">{t.id}</td>
                  <td className="py-2 pr-3 tabular-nums">{t.sale_id}</td>
                  <td className="py-2 pr-3">
                    <Badge variant={t.transaction_type === 'REFUND' ? 'warning' : 'default'}>
                      {t.transaction_type}
                    </Badge>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">
                    {formatMoney(t.amount_cents)}
                  </td>
                  <td className="py-2 text-muted">{formatDateTime(t.occurred_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && transactions.length === 0 && (
        <p className="mt-4 text-sm text-muted">No transactions loaded. Apply filters and click Load.</p>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Drawer Events                                                      */
/* ------------------------------------------------------------------ */

function DrawerEventsSection() {
  const [registerId, setRegisterId] = useState('');
  const [eventType, setEventType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [limit, setLimit] = useState('50');
  const [events, setEvents] = useState<DrawerEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadEvents() {
    if (!registerId.trim()) {
      setError('Register ID is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (eventType.trim()) params.set('event_type', eventType.trim());
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      if (limit.trim()) params.set('limit', limit.trim());

      const res = await api.get<{ events: DrawerEvent[] }>(
        `/api/registers/${registerId.trim()}/events?${params}`,
      );
      setEvents(res.events ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load events.');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardTitle>Drawer Events</CardTitle>

      {error && (
        <div className="mt-3 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
        <Input
          label="Register ID"
          value={registerId}
          onChange={(e) => setRegisterId(e.target.value)}
          placeholder="Required"
        />
        <Input
          label="Event Type"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
          placeholder="e.g. OPEN, CLOSE, DROP"
        />
        <Input
          label="Start Date"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <Input
          label="End Date"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <Input
          label="Limit"
          type="number"
          min="1"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
        />
      </div>

      <div className="mt-4">
        <Button onClick={loadEvents} disabled={loading}>
          {loading ? 'Loading...' : 'Load Events'}
        </Button>
      </div>

      {/* Results */}
      {events.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">Register</th>
                <th className="py-2 pr-3 font-medium">Session</th>
                <th className="py-2 pr-3 font-medium">Type</th>
                <th className="py-2 pr-3 font-medium text-right">Amount</th>
                <th className="py-2 font-medium">Occurred At</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b border-border/50">
                  <td className="py-2 pr-3 tabular-nums">{e.id}</td>
                  <td className="py-2 pr-3 tabular-nums">{e.register_id}</td>
                  <td className="py-2 pr-3 tabular-nums">{e.register_session_id}</td>
                  <td className="py-2 pr-3">
                    <Badge>{e.event_type}</Badge>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-medium">
                    {e.amount_cents != null ? formatMoney(e.amount_cents) : '-'}
                  </td>
                  <td className="py-2 text-muted">{formatDateTime(e.occurred_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && events.length === 0 && (
        <p className="mt-4 text-sm text-muted">No events loaded. Enter a Register ID and click Load.</p>
      )}
    </Card>
  );
}
