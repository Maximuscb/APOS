import { useMemo } from 'react';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, exportToCsv } from './formatters';
import type { ReportFiltersState, VendorSpendRow, CostChangeRow } from './types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

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

export function VendorReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const spend = useReport<{ rows: VendorSpendRow[] }>('/api/reports/vendor-spend', params);
  const costChanges = useReport<{ rows: CostChangeRow[] }>('/api/reports/cost-changes', params);

  const loading = spend.loading || costChanges.loading;

  const refresh = () => {
    spend.refresh();
    costChanges.refresh();
  };

  const totalSpend = spend.data?.rows.reduce((sum, r) => sum + r.total_spend_cents, 0) ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Vendor & Purchasing</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {spend.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{spend.error}</div>
      )}

      {/* Vendor Spend Table */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Vendor Spend</CardTitle>
            <CardDescription>
              {spend.data?.rows.length ?? 0} vendors | Total: {formatMoney(totalSpend)}
            </CardDescription>
          </div>
          {spend.data && spend.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'vendor_name', header: 'Vendor' },
                { key: 'total_documents', header: 'Documents' },
                { key: 'total_line_items', header: 'Line Items' },
                { key: 'total_spend_cents', header: 'Total Spend (cents)' },
              ],
              spend.data.rows,
              'vendor-spend',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'vendor_name', header: 'Vendor' },
              { key: 'total_documents', header: 'Receives', render: (r) => <span className="tabular-nums">{r.total_documents}</span> },
              { key: 'total_line_items', header: 'Line Items', render: (r) => <span className="tabular-nums">{r.total_line_items}</span> },
              { key: 'total_spend_cents', header: 'Total Spend', render: (r) => <span className="tabular-nums font-medium">{formatMoney(r.total_spend_cents)}</span> },
            ]}
            data={spend.data?.rows ?? []}
            emptyMessage="No vendor spend data for selected period."
          />
        </div>
      </Card>

      {/* Cost Changes */}
      {costChanges.data && costChanges.data.rows.length > 0 && (
        <Card>
          <CardTitle>Cost Changes Over Time</CardTitle>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={costChanges.data.rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="occurred_at" tick={{ fontSize: 11 }} tickFormatter={(v) => new Date(v).toLocaleDateString()} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatMoney(v)} />
                <Tooltip
                  formatter={(value: number) => formatMoney(value)}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Line type="monotone" dataKey="unit_cost_cents" stroke="#3b82f6" name="Unit Cost" dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4">
            <DataTable
              columns={[
                { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
                { key: 'name', header: 'Product' },
                { key: 'vendor_name', header: 'Vendor' },
                { key: 'unit_cost_cents', header: 'Unit Cost', render: (r) => <span className="tabular-nums">{formatMoney(r.unit_cost_cents)}</span> },
                { key: 'occurred_at', header: 'Date', render: (r) => <span className="text-muted">{new Date(r.occurred_at).toLocaleDateString()}</span> },
              ]}
              data={costChanges.data.rows}
              emptyMessage="No cost change data."
            />
          </div>
        </Card>
      )}
    </div>
  );
}
