import { useMemo } from 'react';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, pctDisplay, exportToCsv } from './formatters';
import { formatDateTime } from '@/lib/format';
import type { ReportFiltersState, CustomerCLVRow, RetentionReport, RewardsLiabilityReport } from './types';

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

export function CustomerReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const clv = useReport<{ rows: CustomerCLVRow[] }>('/api/reports/customer-clv', params);
  const retention = useReport<RetentionReport>('/api/reports/customer-retention', params);
  const rewards = useReport<RewardsLiabilityReport>('/api/reports/rewards-liability', params);

  const loading = clv.loading || retention.loading || rewards.loading;

  const refresh = () => {
    clv.refresh();
    retention.refresh();
    rewards.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Customer & Rewards</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {clv.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{clv.error}</div>
      )}

      {/* Retention & Rewards Summary */}
      {(retention.data || rewards.data) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {retention.data && (
            <>
              <MetricCard label="Total Customers" value={String(retention.data.total_customers)} />
              <MetricCard label="Repeat Customers" value={String(retention.data.repeat_customers)} />
              <MetricCard label="Repeat Rate" value={pctDisplay(retention.data.repeat_pct)} />
            </>
          )}
          {rewards.data && (
            <>
              <MetricCard label="Reward Accounts" value={String(rewards.data.total_accounts)} />
              <MetricCard label="Outstanding Points" value={String(rewards.data.outstanding_points)} />
              <MetricCard label="Lifetime Earned" value={String(rewards.data.lifetime_earned)} />
              <MetricCard label="Lifetime Redeemed" value={String(rewards.data.lifetime_redeemed)} />
              <MetricCard label="Redemption Rate" value={pctDisplay(rewards.data.redemption_rate_pct)} />
            </>
          )}
        </div>
      )}

      {/* Customer CLV Table */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Customer Lifetime Value</CardTitle>
            <CardDescription>Top customers by total spend</CardDescription>
          </div>
          {clv.data && clv.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'first_name', header: 'First Name' },
                { key: 'last_name', header: 'Last Name' },
                { key: 'email', header: 'Email' },
                { key: 'total_spent_cents', header: 'Total Spent (cents)' },
                { key: 'total_visits', header: 'Visits' },
                { key: 'avg_basket_cents', header: 'Avg Basket (cents)' },
              ],
              clv.data.rows,
              'customer-clv',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'first_name', header: 'Name', render: (r) => `${r.first_name} ${r.last_name}` },
              { key: 'email', header: 'Email', render: (r) => <span className="text-muted">{r.email ?? '-'}</span> },
              { key: 'total_spent_cents', header: 'Total Spent', render: (r) => <span className="tabular-nums font-medium">{formatMoney(r.total_spent_cents)}</span> },
              { key: 'total_visits', header: 'Visits', render: (r) => <span className="tabular-nums">{r.total_visits}</span> },
              { key: 'avg_basket_cents', header: 'Avg Basket', render: (r) => <span className="tabular-nums">{formatMoney(r.avg_basket_cents)}</span> },
              { key: 'last_visit_at', header: 'Last Visit', render: (r) => <span className="text-muted text-xs">{r.last_visit_at ? formatDateTime(r.last_visit_at) : '-'}</span> },
            ]}
            data={clv.data?.rows ?? []}
            emptyMessage="No customer data. Link customers to sales to populate this report."
          />
        </div>
      </Card>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-muted font-medium uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold mt-1 tabular-nums text-slate-900">{value}</p>
    </div>
  );
}
