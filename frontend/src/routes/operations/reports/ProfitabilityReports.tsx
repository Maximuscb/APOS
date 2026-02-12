import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, pctDisplay, exportToCsv } from './formatters';
import type { ReportFiltersState, MarginReport, MarginOutlierRow, DiscountImpactReport } from './types';

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

const ISSUE_VARIANT: Record<string, 'danger' | 'warning' | 'muted'> = {
  COST_EXCEEDS_PRICE: 'danger',
  BELOW_THRESHOLD: 'warning',
  ZERO_COST: 'muted',
  MISSING_COST: 'muted',
};

export function ProfitabilityReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const margin = useReport<MarginReport>('/api/reports/cogs-margin', params);
  const outliers = useReport<{ rows: MarginOutlierRow[] }>('/api/reports/product-margin-outliers', params);
  const discounts = useReport<DiscountImpactReport>('/api/reports/discount-impact', params);

  const loading = margin.loading || outliers.loading || discounts.loading;

  const refresh = () => {
    margin.refresh();
    outliers.refresh();
    discounts.refresh();
  };

  const marginPieData = margin.data
    ? [
        { name: 'COGS', value: margin.data.cogs_cents },
        { name: 'Margin', value: margin.data.margin_cents },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Profitability & Margin</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {margin.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{margin.error}</div>
      )}

      {/* Gross Margin Summary */}
      {margin.data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="grid grid-cols-2 gap-4">
            <MetricCard label="Revenue" value={formatMoney(margin.data.revenue_cents)} />
            <MetricCard label="COGS" value={formatMoney(margin.data.cogs_cents)} />
            <MetricCard label="Gross Margin" value={formatMoney(margin.data.margin_cents)} />
            <MetricCard label="Margin %" value={pctDisplay(margin.data.margin_pct)} />
          </div>
          {marginPieData[0]?.value > 0 && (
            <Card>
              <CardTitle>Revenue Split</CardTitle>
              <div className="h-48 mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={marginPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${name}: ${formatMoney(value)}`}>
                      <Cell fill="#ef4444" />
                      <Cell fill="#10b981" />
                    </Pie>
                    <Tooltip formatter={(value: number) => formatMoney(value)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Product Margin Outliers */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Product Margin Outliers</CardTitle>
            <CardDescription>{outliers.data?.rows.length ?? 0} products flagged</CardDescription>
          </div>
          {outliers.data && outliers.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'sku', header: 'SKU' }, { key: 'name', header: 'Name' },
                { key: 'price_cents', header: 'Price (cents)' }, { key: 'cost_cents', header: 'Cost (cents)' },
                { key: 'margin_pct', header: 'Margin %' }, { key: 'issue', header: 'Issue' },
              ],
              outliers.data.rows,
              'margin-outliers',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'issue', header: 'Issue', render: (r) => <Badge variant={ISSUE_VARIANT[r.issue] ?? 'default'}>{r.issue.replace(/_/g, ' ')}</Badge> },
              { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
              { key: 'name', header: 'Product' },
              { key: 'price_cents', header: 'Price', render: (r) => <span className="tabular-nums">{formatMoney(r.price_cents)}</span> },
              { key: 'cost_cents', header: 'Cost', render: (r) => <span className="tabular-nums">{r.cost_cents != null ? formatMoney(r.cost_cents) : '-'}</span> },
              { key: 'margin_pct', header: 'Margin %', render: (r) => <span className="tabular-nums">{pctDisplay(r.margin_pct)}</span> },
            ]}
            data={outliers.data?.rows ?? []}
            emptyMessage="No margin outliers found."
          />
        </div>
      </Card>

      {/* Discount Impact */}
      {discounts.data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <MetricCard label="Total Discounts" value={formatMoney(discounts.data.total_discount_cents)} variant="warning" />
            <MetricCard label="Lines Discounted" value={String(discounts.data.total_lines_discounted)} />
            <MetricCard label="Margin Erosion" value={formatMoney(discounts.data.margin_erosion_cents)} variant="danger" />
          </div>
          {discounts.data.by_employee.length > 0 && (
            <Card padding={false}>
              <div className="p-5 pb-0">
                <CardTitle>Discount Usage by Employee</CardTitle>
              </div>
              <div className="mt-4">
                <DataTable
                  columns={[
                    { key: 'username', header: 'Employee' },
                    { key: 'discount_count', header: 'Discounts Given', render: (r) => <span className="tabular-nums">{r.discount_count}</span> },
                    { key: 'discount_total_cents', header: 'Total Discount', render: (r) => <span className="tabular-nums">{formatMoney(r.discount_total_cents)}</span> },
                  ]}
                  data={discounts.data.by_employee}
                  emptyMessage="No discount data."
                />
              </div>
            </Card>
          )}
        </>
      )}
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
