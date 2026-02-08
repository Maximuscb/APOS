import { useState } from 'react';
import { api } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

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

type TenderTotals = Record<string, number>;

const TENDER_TYPES = ['CASH', 'CARD', 'CHECK', 'GIFT_CARD', 'STORE_CREDIT'];

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function PaymentsPage() {
  const [activeTab, setActiveTab] = useState('Add Payment');

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Payments</h1>
        <p className="text-sm text-muted mt-1">
          Record payments, look up sale balances, void payments, and view tender summaries.
        </p>
      </div>

      <Tabs
        tabs={['Add Payment', 'Sale Payments', 'Void Payment', 'Tender Summary']}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'Add Payment' && <AddPaymentSection />}
      {activeTab === 'Sale Payments' && <SalePaymentsSection />}
      {activeTab === 'Void Payment' && <VoidPaymentSection />}
      {activeTab === 'Tender Summary' && <TenderSummarySection />}
    </div>
  );
}

/* ================================================================== */
/*  ADD PAYMENT                                                        */
/* ================================================================== */

function AddPaymentSection() {
  const [saleId, setSaleId] = useState('');
  const [tenderType, setTenderType] = useState('CASH');
  const [amountDollars, setAmountDollars] = useState('');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function handleSubmit() {
    if (!saleId.trim()) { setError('Sale ID is required.'); return; }
    const dollars = parseFloat(amountDollars);
    if (Number.isNaN(dollars) || dollars <= 0) { setError('Enter a valid positive amount.'); return; }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = {
        sale_id: Number(saleId),
        tender_type: tenderType,
        amount_cents: Math.round(dollars * 100),
      };
      if (referenceNumber.trim()) body.reference_number = referenceNumber.trim();

      const res = await api.post<{ id: number }>('/api/payments/', body);
      setSuccess(`Payment #${res.id} recorded successfully.`);
      setSaleId('');
      setAmountDollars('');
      setReferenceNumber('');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to record payment.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardTitle>Add Payment</CardTitle>
      <CardDescription>Record a payment against a sale.</CardDescription>

      {error && (
        <div className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <Input
          label="Sale ID"
          type="number"
          min="1"
          value={saleId}
          onChange={(e) => setSaleId(e.target.value)}
          placeholder="Enter sale ID"
        />
        <Select
          label="Tender Type"
          value={tenderType}
          onChange={(e) => setTenderType(e.target.value)}
          options={TENDER_TYPES.map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))}
        />
        <Input
          label="Amount ($)"
          type="number"
          min="0"
          step="0.01"
          value={amountDollars}
          onChange={(e) => setAmountDollars(e.target.value)}
          placeholder="0.00"
        />
        <Input
          label="Reference Number"
          value={referenceNumber}
          onChange={(e) => setReferenceNumber(e.target.value)}
          placeholder="Optional"
        />
      </div>

      <div className="mt-4">
        <Button onClick={handleSubmit} disabled={busy}>
          {busy ? 'Recording...' : 'Record Payment'}
        </Button>
      </div>
    </Card>
  );
}

/* ================================================================== */
/*  SALE PAYMENTS LOOKUP                                               */
/* ================================================================== */

function SalePaymentsSection() {
  const [saleId, setSaleId] = useState('');
  const [includeVoided, setIncludeVoided] = useState(false);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLookup() {
    if (!saleId.trim()) { setError('Enter a sale ID.'); return; }
    setLoading(true);
    setError('');
    setPayments([]);
    setSummary(null);
    try {
      const res = await api.get<{ payments: Payment[]; summary: PaymentSummary }>(
        `/api/payments/sales/${saleId}?include_voided=${includeVoided}`,
      );
      setPayments(res.payments ?? []);
      setSummary(res.summary ?? null);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Lookup failed.');
    } finally {
      setLoading(false);
    }
  }

  function statusBadgeVariant(status: string) {
    switch (status.toUpperCase()) {
      case 'COMPLETED': return 'success' as const;
      case 'VOIDED': return 'danger' as const;
      case 'PENDING': return 'warning' as const;
      default: return 'default' as const;
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle>Sale Payments Lookup</CardTitle>
        <CardDescription>View all payments for a sale and its balance summary.</CardDescription>

        {error && (
          <div className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex flex-wrap gap-4 items-end mt-4">
          <Input
            label="Sale ID"
            type="number"
            min="1"
            value={saleId}
            onChange={(e) => setSaleId(e.target.value)}
            placeholder="Enter sale ID"
            onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Options</label>
            <label className="flex items-center gap-2 h-11 cursor-pointer">
              <input
                type="checkbox"
                checked={includeVoided}
                onChange={(e) => setIncludeVoided(e.target.checked)}
                className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
              />
              <span className="text-sm text-slate-600">Include voided</span>
            </label>
          </div>
          <Button onClick={handleLookup} disabled={loading}>
            {loading ? 'Loading...' : 'Lookup'}
          </Button>
        </div>
      </Card>

      {/* Summary */}
      {summary && (
        <Card>
          <CardTitle>Payment Summary</CardTitle>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mt-4">
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Total Due</p>
              <p className="text-lg font-semibold tabular-nums">{formatMoney(summary.total_due_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Total Paid</p>
              <p className="text-lg font-semibold tabular-nums">{formatMoney(summary.total_paid_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Remaining</p>
              <p className={`text-lg font-semibold tabular-nums ${summary.remaining_cents > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {formatMoney(summary.remaining_cents)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Change Due</p>
              <p className="text-lg font-semibold tabular-nums">{formatMoney(summary.change_due_cents)}</p>
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Status</p>
              <Badge variant={summary.payment_status === 'PAID' ? 'success' : summary.payment_status === 'PARTIAL' ? 'warning' : 'danger'}>
                {summary.payment_status}
              </Badge>
            </div>
          </div>
        </Card>
      )}

      {/* Payments List */}
      {payments.length > 0 && (
        <Card padding={false}>
          <div className="p-5 pb-0">
            <CardTitle>Payments</CardTitle>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 px-5 font-medium">ID</th>
                  <th className="py-2 px-3 font-medium">Tender Type</th>
                  <th className="py-2 px-3 font-medium text-right">Amount</th>
                  <th className="py-2 px-5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-b border-border/50 hover:bg-slate-50">
                    <td className="py-2.5 px-5 tabular-nums">{p.id}</td>
                    <td className="py-2.5 px-3">{p.tender_type.replace(/_/g, ' ')}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums font-medium">
                      {formatMoney(p.amount_cents)}
                    </td>
                    <td className="py-2.5 px-5">
                      <Badge variant={statusBadgeVariant(p.status)}>{p.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ================================================================== */
/*  VOID PAYMENT                                                       */
/* ================================================================== */

function VoidPaymentSection() {
  const [paymentId, setPaymentId] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function handleVoid() {
    if (!paymentId.trim()) { setError('Payment ID is required.'); return; }
    if (!reason.trim()) { setError('Reason is required.'); return; }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/payments/${paymentId}/void`, { reason: reason.trim() });
      setSuccess(`Payment #${paymentId} voided successfully.`);
      setPaymentId('');
      setReason('');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to void payment.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardTitle>Void Payment</CardTitle>
      <CardDescription>Void an existing payment by ID.</CardDescription>

      {error && (
        <div className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <Input
          label="Payment ID"
          type="number"
          min="1"
          value={paymentId}
          onChange={(e) => setPaymentId(e.target.value)}
          placeholder="Enter payment ID"
        />
        <Input
          label="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for voiding"
        />
      </div>

      <div className="mt-4">
        <Button variant="danger" onClick={handleVoid} disabled={busy}>
          {busy ? 'Voiding...' : 'Void Payment'}
        </Button>
      </div>
    </Card>
  );
}

/* ================================================================== */
/*  TENDER SUMMARY                                                     */
/* ================================================================== */

function TenderSummarySection() {
  const [sessionId, setSessionId] = useState('');
  const [totals, setTotals] = useState<TenderTotals | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLoad() {
    if (!sessionId.trim()) { setError('Session ID is required.'); return; }
    setLoading(true);
    setError('');
    setTotals(null);
    try {
      const res = await api.get<{ tender_totals_cents: TenderTotals }>(
        `/api/payments/sessions/${sessionId}/tender-summary`,
      );
      setTotals(res.tender_totals_cents ?? {});
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load tender summary.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle>Tender Summary</CardTitle>
        <CardDescription>View tender totals by type for a register session.</CardDescription>

        {error && (
          <div className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex flex-wrap gap-4 items-end mt-4">
          <Input
            label="Session ID"
            type="number"
            min="1"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Enter session ID"
            onKeyDown={(e) => e.key === 'Enter' && handleLoad()}
          />
          <Button onClick={handleLoad} disabled={loading}>
            {loading ? 'Loading...' : 'Load Summary'}
          </Button>
        </div>
      </Card>

      {totals && (
        <Card>
          <CardTitle>Totals by Tender Type</CardTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-4">
            {Object.entries(totals).map(([type, cents]) => (
              <div key={type} className="rounded-xl bg-slate-50 border border-border p-4">
                <p className="text-xs text-muted uppercase tracking-wider">{type.replace(/_/g, ' ')}</p>
                <p className="text-xl font-semibold tabular-nums mt-1">{formatMoney(cents)}</p>
              </div>
            ))}
          </div>
          {Object.keys(totals).length === 0 && (
            <p className="text-sm text-muted mt-4">No tender totals found for this session.</p>
          )}
        </Card>
      )}
    </div>
  );
}
