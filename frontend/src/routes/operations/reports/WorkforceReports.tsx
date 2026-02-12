import { useMemo } from 'react';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, minutesToHours, exportToCsv } from './formatters';
import type { ReportFiltersState, LaborHoursRow, LaborVsSalesReport, EmployeePerformanceRow } from './types';

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

export function WorkforceReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const laborHours = useReport<{ rows: LaborHoursRow[] }>('/api/reports/labor-hours', params);
  const laborVsSales = useReport<LaborVsSalesReport>('/api/reports/labor-vs-sales', params);
  const performance = useReport<{ rows: EmployeePerformanceRow[] }>('/api/reports/employee-performance', params);

  const loading = laborHours.loading || laborVsSales.loading || performance.loading;

  const refresh = () => {
    laborHours.refresh();
    laborVsSales.refresh();
    performance.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Employee / Workforce</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {laborHours.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{laborHours.error}</div>
      )}

      {/* Labor vs Sales Summary */}
      {laborVsSales.data && (
        <div className="grid grid-cols-3 gap-4">
          <MetricCard label="Total Labor Hours" value={minutesToHours(laborVsSales.data.total_labor_minutes)} />
          <MetricCard label="Total Revenue" value={formatMoney(laborVsSales.data.total_revenue_cents)} />
          <MetricCard label="Revenue / Labor Hour" value={formatMoney(laborVsSales.data.revenue_per_labor_hour_cents)} />
        </div>
      )}

      {/* Labor Hours Table */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Timekeeping Summary</CardTitle>
            <CardDescription>{laborHours.data?.rows.length ?? 0} employees</CardDescription>
          </div>
          {laborHours.data && laborHours.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'username', header: 'Employee' },
                { key: 'total_entries', header: 'Shifts' },
                { key: 'total_worked_minutes', header: 'Worked (min)' },
                { key: 'total_break_minutes', header: 'Break (min)' },
                { key: 'net_worked_minutes', header: 'Net (min)' },
                { key: 'overtime_flag', header: 'Overtime' },
                { key: 'missed_punches', header: 'Missed Punches' },
              ],
              laborHours.data.rows,
              'labor-hours',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'username', header: 'Employee' },
              { key: 'total_entries', header: 'Shifts', render: (r) => <span className="tabular-nums">{r.total_entries}</span> },
              { key: 'total_worked_minutes', header: 'Worked', render: (r) => <span className="tabular-nums">{minutesToHours(r.total_worked_minutes)}</span> },
              { key: 'total_break_minutes', header: 'Breaks', render: (r) => <span className="tabular-nums">{minutesToHours(r.total_break_minutes)}</span> },
              { key: 'net_worked_minutes', header: 'Net', render: (r) => <span className="tabular-nums">{minutesToHours(r.net_worked_minutes)}</span> },
              { key: 'overtime_flag', header: 'OT', render: (r) => r.overtime_flag ? <Badge variant="warning">OT</Badge> : <span className="text-muted">-</span> },
              { key: 'missed_punches', header: 'Missed', render: (r) => r.missed_punches > 0 ? <Badge variant="danger">{r.missed_punches}</Badge> : <span className="text-muted">0</span> },
            ]}
            data={laborHours.data?.rows ?? []}
            emptyMessage="No timekeeping data for selected period."
          />
        </div>
      </Card>

      {/* Employee Performance */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Employee Performance</CardTitle>
          <CardDescription>Sales, discounts, and refunds by employee</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'username', header: 'Employee' },
              { key: 'sales_count', header: 'Sales', render: (r) => <span className="tabular-nums">{r.sales_count}</span> },
              { key: 'gross_sales_cents', header: 'Gross Sales', render: (r) => <span className="tabular-nums">{formatMoney(r.gross_sales_cents)}</span> },
              { key: 'avg_ticket_cents', header: 'Avg Ticket', render: (r) => <span className="tabular-nums">{formatMoney(r.avg_ticket_cents)}</span> },
              { key: 'discount_count', header: 'Discounts', render: (r) => <span className="tabular-nums">{r.discount_count}</span> },
              { key: 'discount_total_cents', header: 'Disc. $', render: (r) => <span className="tabular-nums">{formatMoney(r.discount_total_cents)}</span> },
              { key: 'refund_count', header: 'Refunds', render: (r) => r.refund_count > 0 ? <Badge variant="warning">{r.refund_count}</Badge> : <span className="text-muted">0</span> },
              { key: 'refund_total_cents', header: 'Refund $', render: (r) => <span className="tabular-nums">{formatMoney(r.refund_total_cents)}</span> },
            ]}
            data={performance.data?.rows ?? []}
            emptyMessage="No performance data for selected period."
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
