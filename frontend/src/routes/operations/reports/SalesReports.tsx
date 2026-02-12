import { useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Tabs } from '@/components/ui/Tabs';
import { Select } from '@/components/ui/Input';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, pctDisplay, exportToCsv } from './formatters';
import { Button } from '@/components/ui/Button';
import type {
  ReportFiltersState,
  SalesSummary,
  SalesByTimeReport,
  SalesByProductRow,
  SalesByEmployeeRow,
  SalesByStoreRow,
} from './types';

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

interface Props {
  filters: ReportFiltersState;
  onFiltersChange: (f: ReportFiltersState) => void;
}

function buildParams(filters: ReportFiltersState, extra?: Record<string, string>) {
  const p: Record<string, string> = {};
  if (filters.storeId) p.store_id = filters.storeId;
  if (filters.includeChildren) p.include_children = 'true';
  if (filters.startDate) p.start = new Date(filters.startDate).toISOString();
  if (filters.endDate) p.end = new Date(filters.endDate).toISOString();
  return { ...p, ...extra };
}

function safeMoney(value: unknown): string {
  return formatMoney(typeof value === 'number' && Number.isFinite(value) ? value : 0);
}

export function SalesReports({ filters, onFiltersChange }: Props) {
  const [subTab, setSubTab] = useState('summary');
  const [timeMode, setTimeMode] = useState('hourly');

  const params = useMemo(() => buildParams(filters), [filters]);
  const timeParams = useMemo(() => buildParams(filters, { mode: timeMode }), [filters, timeMode]);

  const summary = useReport<SalesSummary>('/api/reports/sales-summary', params);
  const byTime = useReport<SalesByTimeReport>('/api/reports/sales-by-time', timeParams, { enabled: subTab === 'time' });
  const byProduct = useReport<{ rows: SalesByProductRow[]; total_revenue_cents: number }>('/api/reports/abc-analysis', params, { enabled: subTab === 'product' });
  const byEmployee = useReport<{ rows: SalesByEmployeeRow[] }>('/api/reports/sales-by-employee', params, { enabled: subTab === 'employee' });
  const byStore = useReport<{ rows: SalesByStoreRow[] }>('/api/reports/sales-by-store', params, { enabled: subTab === 'store' });

  const loading = summary.loading || byTime.loading || byProduct.loading || byEmployee.loading || byStore.loading;

  const refresh = () => {
    summary.refresh();
    if (subTab === 'time') byTime.refresh();
    if (subTab === 'product') byProduct.refresh();
    if (subTab === 'employee') byEmployee.refresh();
    if (subTab === 'store') byStore.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Sales & Revenue</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {summary.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{summary.error}</div>
      )}

      {/* Summary Cards */}
      {summary.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Gross Sales" value={formatMoney(summary.data.gross_sales_cents)} />
          <MetricCard label="Net Sales" value={formatMoney(summary.data.net_sales_cents)} />
          <MetricCard label="Returns" value={formatMoney(summary.data.return_total_cents)} variant="danger" />
          <MetricCard label="Avg Ticket" value={formatMoney(summary.data.avg_ticket_cents)} />
          <MetricCard label="Transactions" value={String(summary.data.transaction_count)} />
          <MetricCard label="Items Sold" value={String(summary.data.items_sold)} />
          <MetricCard label="Tax Collected" value={formatMoney(summary.data.tax_collected_cents)} />
          <MetricCard label="Discounts" value={formatMoney(summary.data.discount_total_cents)} variant="warning" />
        </div>
      )}

      {/* Payment Breakdown Pie */}
      {summary.data && summary.data.payment_breakdown.length > 0 && (
        <Card>
          <CardTitle>Payment Method Breakdown</CardTitle>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={summary.data.payment_breakdown}
                  dataKey="total_cents"
                  nameKey="tender_type"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={(entry: any) => `${entry?.tender_type ?? 'Unknown'}: ${safeMoney(entry?.total_cents)}`}
                >
                  {summary.data.payment_breakdown.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip formatter={(value: unknown) => safeMoney(value)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {/* Sub-tabs */}
      <Tabs
        tabs={[
          { value: 'summary', label: 'Time Trends' },
          { value: 'time', label: 'Sales by Time' },
          { value: 'product', label: 'By Product' },
          { value: 'employee', label: 'By Employee' },
          { value: 'store', label: 'By Store' },
        ]}
        value={subTab}
        onValueChange={setSubTab}
      />

      {/* Time Trends (existing sales report) */}
      {subTab === 'summary' && <SalesTimeTrends params={params} />}

      {/* Sales by Time */}
      {subTab === 'time' && (
        <Card>
          <div className="flex items-center justify-between">
            <CardTitle>Sales by Time</CardTitle>
            <Select
              label=""
              value={timeMode}
              onChange={(e) => setTimeMode(e.target.value)}
              options={[
                { value: 'hourly', label: 'Hourly' },
                { value: 'day_of_week', label: 'Day of Week' },
                { value: 'monthly', label: 'Monthly' },
              ]}
            />
          </div>
          {byTime.data && byTime.data.rows.length > 0 ? (
            <div className="h-72 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byTime.data.rows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => safeMoney(v)} />
                  <Tooltip formatter={(value: unknown) => safeMoney(value)} />
                  <Bar dataKey="gross_sales_cents" fill="#3b82f6" name="Sales" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-muted mt-4">No data for selected period.</p>
          )}
        </Card>
      )}

      {/* Sales by Product */}
      {subTab === 'product' && (
        <Card padding={false}>
          <div className="p-5 pb-0 flex items-center justify-between">
            <div>
              <CardTitle>Sales by Product (ABC Analysis)</CardTitle>
              <CardDescription>
                {byProduct.data?.rows.length ?? 0} products | Total: {formatMoney(byProduct.data?.total_revenue_cents ?? 0)}
              </CardDescription>
            </div>
            {byProduct.data && (
              <Button variant="ghost" onClick={() => exportToCsv(
                [
                  { key: 'sku', header: 'SKU' },
                  { key: 'name', header: 'Name' },
                  { key: 'units_sold', header: 'Units' },
                  { key: 'revenue_cents', header: 'Revenue (cents)' },
                  { key: 'share_pct', header: 'Share %' },
                  { key: 'category', header: 'ABC' },
                ],
                byProduct.data.rows,
                'sales-by-product',
              )}>
                Export CSV
              </Button>
            )}
          </div>
          <div className="mt-4">
            <DataTable
              columns={[
                { key: 'category', header: 'ABC', render: (r) => <Badge variant={r.category === 'A' ? 'success' : r.category === 'B' ? 'warning' : 'muted'}>{r.category}</Badge> },
                { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
                { key: 'name', header: 'Product' },
                { key: 'units_sold', header: 'Units', render: (r) => <span className="tabular-nums">{r.units_sold}</span> },
                { key: 'revenue_cents', header: 'Revenue', render: (r) => <span className="tabular-nums">{formatMoney(r.revenue_cents)}</span> },
                { key: 'share_pct', header: 'Share', render: (r) => <span className="tabular-nums">{pctDisplay(r.share_pct)}</span> },
              ]}
              data={byProduct.data?.rows ?? []}
              emptyMessage="No product data for selected period."
            />
          </div>
        </Card>
      )}

      {/* Sales by Employee */}
      {subTab === 'employee' && (
        <Card padding={false}>
          <div className="p-5 pb-0">
            <CardTitle>Sales by Employee</CardTitle>
          </div>
          <div className="mt-4">
            <DataTable
              columns={[
                { key: 'username', header: 'Employee' },
                { key: 'sales_count', header: 'Sales', render: (r) => <span className="tabular-nums">{r.sales_count}</span> },
                { key: 'gross_sales_cents', header: 'Gross Sales', render: (r) => <span className="tabular-nums">{formatMoney(r.gross_sales_cents)}</span> },
                { key: 'avg_ticket_cents', header: 'Avg Ticket', render: (r) => <span className="tabular-nums">{formatMoney(r.avg_ticket_cents)}</span> },
                { key: 'refund_count', header: 'Refunds', render: (r) => <span className="tabular-nums">{r.refund_count}</span> },
                { key: 'discount_total_cents', header: 'Discounts', render: (r) => <span className="tabular-nums">{formatMoney(r.discount_total_cents)}</span> },
              ]}
              data={byEmployee.data?.rows ?? []}
              emptyMessage="No employee data for selected period."
            />
          </div>
        </Card>
      )}

      {/* Sales by Store */}
      {subTab === 'store' && (
        <Card padding={false}>
          <div className="p-5 pb-0">
            <CardTitle>Sales by Store</CardTitle>
          </div>
          <div className="mt-4">
            <DataTable
              columns={[
                { key: 'store_name', header: 'Store' },
                { key: 'transaction_count', header: 'Transactions', render: (r) => <span className="tabular-nums">{r.transaction_count}</span> },
                { key: 'gross_sales_cents', header: 'Gross Sales', render: (r) => <span className="tabular-nums">{formatMoney(r.gross_sales_cents)}</span> },
                { key: 'cogs_cents', header: 'COGS', render: (r) => <span className="tabular-nums">{formatMoney(r.cogs_cents)}</span> },
                { key: 'margin_cents', header: 'Margin', render: (r) => <span className="tabular-nums">{formatMoney(r.margin_cents)}</span> },
                { key: 'margin_pct', header: 'Margin %', render: (r) => <span className="tabular-nums">{pctDisplay(r.margin_pct)}</span> },
              ]}
              data={byStore.data?.rows ?? []}
              emptyMessage="No multi-store data available."
            />
          </div>
        </Card>
      )}
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────── */

function MetricCard({ label, value, variant }: { label: string; value: string; variant?: 'danger' | 'warning' }) {
  const color = variant === 'danger' ? 'text-red-600' : variant === 'warning' ? 'text-amber-600' : 'text-slate-900';
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-muted font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

function SalesTimeTrends({ params }: { params: Record<string, string> }) {
  const report = useReport<{ rows: { period: string; sales_count: number; gross_sales_cents: number; items_sold: number }[] }>(
    '/api/reports/sales',
    { ...params, group_by: 'day' },
  );

  if (report.loading) return <div className="text-sm text-muted p-4">Loading trends...</div>;
  if (!report.data || report.data.rows.length === 0) return <Card><p className="text-sm text-muted">No trend data for selected period.</p></Card>;

  return (
    <Card>
      <CardTitle>Daily Sales Trend</CardTitle>
      <div className="h-72 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={report.data.rows}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="period" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => safeMoney(v)} />
            <Tooltip formatter={(value: unknown, name: string) => [safeMoney(value), name === 'gross_sales_cents' ? 'Sales' : name]} />
            <Bar dataKey="gross_sales_cents" fill="#3b82f6" name="Sales" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
