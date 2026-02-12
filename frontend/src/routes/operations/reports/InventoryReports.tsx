import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, exportToCsv } from './formatters';
import type { ReportFiltersState, InventoryValuationRow, LowStockRow, ShrinkageReport, InventoryMovementRow } from './types';

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

export function InventoryReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const valuation = useReport<{ total_value_cents: number; rows: InventoryValuationRow[] }>('/api/reports/inventory-valuation', params);
  const lowStock = useReport<{ rows: LowStockRow[] }>('/api/reports/low-stock', { ...params, threshold: '10' });
  const deadStock = useReport<{ slow_moving: { sku: string; name: string; days_since_last_sale: number }[]; dead_stock: { sku: string; name: string; days_since_last_sale: number }[]; never_sold: { sku: string; name: string }[] }>('/api/reports/slow-dead-stock', params);
  const shrinkage = useReport<ShrinkageReport>('/api/reports/shrinkage', params);
  const movement = useReport<{ rows: InventoryMovementRow[] }>('/api/reports/inventory-movement', params);

  const loading = valuation.loading || lowStock.loading || deadStock.loading || shrinkage.loading || movement.loading;

  const refresh = () => {
    valuation.refresh();
    lowStock.refresh();
    deadStock.refresh();
    shrinkage.refresh();
    movement.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Inventory Reports</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {valuation.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{valuation.error}</div>
      )}

      {/* Valuation Summary */}
      {valuation.data && (
        <div className="grid grid-cols-2 gap-4">
          <MetricCard label="Total Inventory Value" value={formatMoney(valuation.data.total_value_cents)} />
          <MetricCard label="Active Products" value={String(valuation.data.rows.length)} />
        </div>
      )}

      {/* Inventory Valuation Table */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Inventory Valuation</CardTitle>
            <CardDescription>{valuation.data?.rows.length ?? 0} products</CardDescription>
          </div>
          {valuation.data && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'sku', header: 'SKU' }, { key: 'name', header: 'Name' },
                { key: 'quantity_on_hand', header: 'QOH' },
                { key: 'weighted_average_cost_cents', header: 'WAC (cents)' },
                { key: 'inventory_value_cents', header: 'Value (cents)' },
              ],
              valuation.data.rows,
              'inventory-valuation',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
              { key: 'name', header: 'Product' },
              { key: 'quantity_on_hand', header: 'QOH', render: (r) => <span className="tabular-nums">{r.quantity_on_hand}</span> },
              { key: 'weighted_average_cost_cents', header: 'WAC', render: (r) => <span className="tabular-nums">{r.weighted_average_cost_cents != null ? formatMoney(r.weighted_average_cost_cents) : '-'}</span> },
              { key: 'inventory_value_cents', header: 'Value', render: (r) => <span className="tabular-nums">{r.inventory_value_cents != null ? formatMoney(r.inventory_value_cents) : '-'}</span> },
            ]}
            data={valuation.data?.rows ?? []}
            emptyMessage="No inventory data."
          />
        </div>
      </Card>

      {/* Low Stock */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Low Stock Alert</CardTitle>
          <CardDescription>{lowStock.data?.rows.length ?? 0} products below threshold</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
              { key: 'name', header: 'Product' },
              { key: 'quantity_on_hand', header: 'QOH', render: (r) => <Badge variant={r.quantity_on_hand <= 0 ? 'danger' : 'warning'}>{r.quantity_on_hand}</Badge> },
            ]}
            data={lowStock.data?.rows ?? []}
            emptyMessage="No low stock items."
          />
        </div>
      </Card>

      {/* Dead / Slow Stock */}
      {deadStock.data && (
        <Card padding={false}>
          <div className="p-5 pb-0">
            <CardTitle>Dead & Slow Stock</CardTitle>
            <CardDescription>
              {deadStock.data.dead_stock.length} dead | {deadStock.data.slow_moving.length} slow | {deadStock.data.never_sold.length} never sold
            </CardDescription>
          </div>
          <div className="mt-4">
            <DataTable
              columns={[
                { key: 'status', header: 'Status', render: (r: { sku: string; name: string; days_since_last_sale?: number }) => (
                  <Badge variant={r.days_since_last_sale == null ? 'muted' : (r.days_since_last_sale ?? 0) >= 90 ? 'danger' : 'warning'}>
                    {r.days_since_last_sale == null ? 'Never Sold' : (r.days_since_last_sale ?? 0) >= 90 ? 'Dead' : 'Slow'}
                  </Badge>
                )},
                { key: 'sku', header: 'SKU', render: (r) => <span className="font-mono text-xs">{r.sku}</span> },
                { key: 'name', header: 'Product' },
                { key: 'days_since_last_sale', header: 'Days Since Sale', render: (r: { days_since_last_sale?: number }) => <span className="tabular-nums">{r.days_since_last_sale ?? '-'}</span> },
              ]}
              data={[
                ...deadStock.data.dead_stock,
                ...deadStock.data.slow_moving,
                ...deadStock.data.never_sold.map((n) => ({ ...n, days_since_last_sale: undefined as number | undefined })),
              ]}
              emptyMessage="No dead or slow stock."
            />
          </div>
        </Card>
      )}

      {/* Shrinkage */}
      {shrinkage.data && (
        <div className="grid grid-cols-3 gap-4">
          <MetricCard label="Total Counts" value={String(shrinkage.data.total_counts)} />
          <MetricCard label="Variance Units" value={String(shrinkage.data.total_variance_units)} variant={shrinkage.data.total_variance_units < 0 ? 'danger' : undefined} />
          <MetricCard label="Variance Cost" value={formatMoney(shrinkage.data.total_variance_cost_cents)} variant={shrinkage.data.total_variance_cost_cents < 0 ? 'danger' : undefined} />
        </div>
      )}

      {/* Inventory Movement */}
      {movement.data && movement.data.rows.length > 0 && (
        <Card>
          <CardTitle>Inventory Movement by Type</CardTitle>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={movement.data.rows} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="type" tick={{ fontSize: 11 }} width={80} />
                <Tooltip formatter={(value: unknown) => Math.abs(typeof value === 'number' ? value : 0)} />
                <Bar dataKey="total_units" fill="#3b82f6" name="Units" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
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
