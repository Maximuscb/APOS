import { useMemo } from 'react';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ReportFilters } from './ReportFilters';
import { useReport } from './useReport';
import { formatMoney, exportToCsv } from './formatters';
import { formatDateTime } from '@/lib/format';
import type { ReportFiltersState, RefundAuditRow, PriceOverrideRow, VoidAuditRow, SuspiciousActivityItem } from './types';

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

const CATEGORY_VARIANT: Record<string, 'danger' | 'warning' | 'muted'> = {
  NO_SALE_DRAWER: 'warning',
  FAILED_AUTH: 'danger',
  HIGH_VOIDS: 'danger',
  CASH_VARIANCE: 'warning',
  EXCESSIVE_DISCOUNTS: 'warning',
};

export function RiskReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const refunds = useReport<{ rows: RefundAuditRow[] }>('/api/reports/refund-audit', params);
  const overrides = useReport<{ rows: PriceOverrideRow[] }>('/api/reports/price-overrides', params);
  const voids = useReport<{ rows: VoidAuditRow[] }>('/api/reports/void-audit', params);
  const suspicious = useReport<{ items: SuspiciousActivityItem[] }>('/api/reports/suspicious-activity', params);

  const loading = refunds.loading || overrides.loading || voids.loading || suspicious.loading;

  const refresh = () => {
    refunds.refresh();
    overrides.refresh();
    voids.refresh();
    suspicious.refresh();
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardTitle>Risk / Compliance / Controls</CardTitle>
        <div className="mt-4">
          <ReportFilters filters={filters} onChange={onFiltersChange} onRun={refresh} loading={loading} />
        </div>
      </Card>

      {refunds.error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{refunds.error}</div>
      )}

      {/* Suspicious Activity Flags */}
      {suspicious.data && suspicious.data.items.length > 0 && (
        <Card>
          <CardTitle>Suspicious Activity Flags</CardTitle>
          <div className="mt-4 flex flex-col gap-3">
            {suspicious.data.items.map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
                <Badge variant={CATEGORY_VARIANT[item.category] ?? 'default'}>{item.category.replace(/_/g, ' ')}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900">{item.description}</p>
                  <p className="text-xs text-muted mt-0.5">{item.details}</p>
                </div>
                <span className="text-sm font-bold tabular-nums text-slate-700">{item.count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Refund Audit */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <div>
            <CardTitle>Refund Audit</CardTitle>
            <CardDescription>{refunds.data?.rows.length ?? 0} refunds</CardDescription>
          </div>
          {refunds.data && refunds.data.rows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'document_number', header: 'Doc #' },
                { key: 'username', header: 'Employee' },
                { key: 'refund_amount_cents', header: 'Amount (cents)' },
                { key: 'reason', header: 'Reason' },
                { key: 'created_at', header: 'Date' },
              ],
              refunds.data.rows,
              'refund-audit',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'document_number', header: 'Doc #', render: (r) => <span className="font-mono text-xs">{r.document_number ?? '-'}</span> },
              { key: 'username', header: 'Employee' },
              { key: 'refund_amount_cents', header: 'Amount', render: (r) => <span className="tabular-nums text-red-600">{formatMoney(r.refund_amount_cents)}</span> },
              { key: 'reason', header: 'Reason', render: (r) => <span className="text-muted text-xs">{r.reason ?? '-'}</span> },
              { key: 'created_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{formatDateTime(r.created_at)}</span> },
            ]}
            data={refunds.data?.rows ?? []}
            emptyMessage="No refunds for selected period."
          />
        </div>
      </Card>

      {/* Price Overrides */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Price Overrides</CardTitle>
          <CardDescription>{overrides.data?.rows.length ?? 0} overrides</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'sale_document_number', header: 'Sale #', render: (r) => <span className="font-mono text-xs">{r.sale_document_number}</span> },
              { key: 'product_name', header: 'Product' },
              { key: 'original_price_cents', header: 'Original', render: (r) => <span className="tabular-nums">{formatMoney(r.original_price_cents)}</span> },
              { key: 'unit_price_cents', header: 'Sold At', render: (r) => <span className="tabular-nums">{formatMoney(r.unit_price_cents)}</span> },
              { key: 'discount_cents', header: 'Discount', render: (r) => <span className="tabular-nums text-amber-600">{formatMoney(r.discount_cents)}</span> },
              { key: 'username', header: 'By' },
              { key: 'approved_by_username', header: 'Approved By', render: (r) => <span className="text-muted">{r.approved_by_username ?? '-'}</span> },
              { key: 'created_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{formatDateTime(r.created_at)}</span> },
            ]}
            data={overrides.data?.rows ?? []}
            emptyMessage="No price overrides for selected period."
          />
        </div>
      </Card>

      {/* Void Audit */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Void Report</CardTitle>
          <CardDescription>{voids.data?.rows.length ?? 0} voided transactions</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'document_number', header: 'Doc #', render: (r) => <span className="font-mono text-xs">{r.document_number}</span> },
              { key: 'original_amount_cents', header: 'Amount', render: (r) => <span className="tabular-nums">{formatMoney(r.original_amount_cents)}</span> },
              { key: 'voided_by_username', header: 'Voided By' },
              { key: 'void_reason', header: 'Reason', render: (r) => <span className="text-muted text-xs">{r.void_reason ?? '-'}</span> },
              { key: 'voided_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{formatDateTime(r.voided_at)}</span> },
            ]}
            data={voids.data?.rows ?? []}
            emptyMessage="No voided transactions for selected period."
          />
        </div>
      </Card>
    </div>
  );
}
