import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, pctDisplay, exportToCsv } from './formatters';
import { formatDateTime } from '@/lib/format';
import type { ReportFiltersState, RegisterReconRow, PaymentBreakdownRow, OverShortReport } from './types';

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

interface Props {
  filters: ReportFiltersState;
  onFiltersChange: (f: ReportFiltersState) => void;
}

function buildParams(filters: ReportFiltersState) {
  const p: Record<string, string> = {};
  if (filters.storeId) p.store_id = filters.storeId;
  if (filters.includeChildren) p.include_children = 'true';
  if (filters.startDate) p.start = new Date(filters.startDate).toISOString();
  if (filters.endDate) p.end = new Date(filters.endDate).toISOString();
  return p;
}

export function CashRegisterReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const recon = useReport<{ rows: RegisterReconRow[] }>('/api/reports/register-reconciliation', params);
  const payments = useReport<{ rows: PaymentBreakdownRow[] }>('/api/reports/payment-breakdown', params);
  const overShort = useReport<OverShortReport>('/api/reports/over-short', params);

  const loading = recon.loading || payments.loading || overShort.loading;

  const refresh = () => {
    recon.refresh();
    payments.refresh();
    overShort.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Cash & Register</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {recon.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{recon.error}</div>
      )}

      {/* Over/Short Summary */}
      {overShort.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total Sessions" value={String(overShort.data.total_sessions)} />
          <MetricCard label="Total Variance" value={formatMoney(overShort.data.total_variance_cents)} variant={overShort.data.total_variance_cents < 0 ? 'danger' : undefined} />
          <MetricCard label="Sessions Over" value={String(overShort.data.sessions_over)} />
          <MetricCard label="Sessions Short" value={String(overShort.data.sessions_short)} variant={overShort.data.sessions_short > 0 ? 'danger' : undefined} />
        </div>
      )}

      {/* Payment Breakdown */}
      {payments.data && payments.data.rows.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardTitle>Payment Methods</CardTitle>
            <div className="h-56 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={payments.data.rows}
                    dataKey="total_cents"
                    nameKey="tender_type"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label={({ tender_type }) => tender_type}
                  >
                    {payments.data.rows.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => formatMoney(value)} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card padding={false}>
            <div className="p-5 pb-0">
              <CardTitle>Payment Detail</CardTitle>
            </div>
            <div className="mt-4">
              <DataTable
                columns={[
                  { key: 'tender_type', header: 'Method' },
                  { key: 'count', header: 'Count', render: (r) => <span className="tabular-nums">{r.count}</span> },
                  { key: 'total_cents', header: 'Total', render: (r) => <span className="tabular-nums">{formatMoney(r.total_cents)}</span> },
                  { key: 'pct_of_total', header: '%', render: (r) => <span className="tabular-nums">{pctDisplay(r.pct_of_total)}</span> },
                ]}
                data={payments.data.rows}
                emptyMessage="No payment data."
              />
            </div>
          </Card>
        </div>
      )}

      {/* Register Reconciliation */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Register Reconciliation</CardTitle>
            <CardDescription>{recon.data?.rows.length ?? 0} closed sessions</CardDescription>
          </div>
          {recon.data && recon.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'register_name', header: 'Register' }, { key: 'username', header: 'Cashier' },
                { key: 'opened_at', header: 'Opened' }, { key: 'closed_at', header: 'Closed' },
                { key: 'opening_cash_cents', header: 'Opening (cents)' },
                { key: 'closing_cash_cents', header: 'Closing (cents)' },
                { key: 'expected_cash_cents', header: 'Expected (cents)' },
                { key: 'variance_cents', header: 'Variance (cents)' },
              ],
              recon.data.rows,
              'register-reconciliation',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'register_name', header: 'Register' },
              { key: 'username', header: 'Cashier' },
              { key: 'opened_at', header: 'Opened', render: (r) => <span className="text-muted text-xs">{formatDateTime(r.opened_at)}</span> },
              { key: 'closed_at', header: 'Closed', render: (r) => <span className="text-muted text-xs">{r.closed_at ? formatDateTime(r.closed_at) : '-'}</span> },
              { key: 'opening_cash_cents', header: 'Opening', render: (r) => <span className="tabular-nums">{formatMoney(r.opening_cash_cents)}</span> },
              { key: 'expected_cash_cents', header: 'Expected', render: (r) => <span className="tabular-nums">{r.expected_cash_cents != null ? formatMoney(r.expected_cash_cents) : '-'}</span> },
              { key: 'closing_cash_cents', header: 'Closing', render: (r) => <span className="tabular-nums">{r.closing_cash_cents != null ? formatMoney(r.closing_cash_cents) : '-'}</span> },
              {
                key: 'variance_cents', header: 'Variance', render: (r) => {
                  if (r.variance_cents == null) return <span className="text-muted">-</span>;
                  const variant = r.variance_cents < 0 ? 'danger' : r.variance_cents > 0 ? 'warning' : 'success';
                  return <Badge variant={variant}>{formatMoney(r.variance_cents)}</Badge>;
                },
              },
            ]}
            data={recon.data?.rows ?? []}
            emptyMessage="No register sessions for selected period."
          />
        </div>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, variant }: { label: string; value: string; variant?: 'danger' | 'warning' }) {
  const color = variant === 'danger' ? 'text-red-600' : variant === 'warning' ? 'text-amber-600' : 'text-slate-900';
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-muted font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 tabular-nums ${color}`}>{value}</p>
    </div>
  );
}
