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

interface SuspiciousActivityApi {
  no_sale_opens?: Array<{ user_id: number | null; username: string | null; count: number }>;
  failed_auth_attempts?: Array<{ user_id: number | null; count: number }>;
  high_void_users?: Array<{ user_id: number | null; username: string | null; void_count: number }>;
  cash_variances?: Array<{ user_id: number | null; username: string | null; register_name: string | null; variance_cents: number; closed_at: string | null }>;
}

function safeMoney(value: unknown): string {
  return formatMoney(typeof value === 'number' && Number.isFinite(value) ? value : 0);
}

function safeDate(value: unknown): string {
  if (!value || typeof value !== 'string') return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '-';
  return formatDateTime(value);
}

export function RiskReports({ filters, onFiltersChange }: Props) {
  const params = useMemo(() => buildParams(filters), [filters]);

  const refunds = useReport<{ rows: RefundAuditRow[] }>('/api/reports/refund-audit', params);
  const overrides = useReport<{ rows: PriceOverrideRow[] }>('/api/reports/price-overrides', params);
  const voids = useReport<{ rows: VoidAuditRow[] }>('/api/reports/void-audit', params);
  const suspicious = useReport<SuspiciousActivityApi>('/api/reports/suspicious-activity', params);

  const loading = refunds.loading || overrides.loading || voids.loading || suspicious.loading;

  const refresh = () => {
    refunds.refresh();
    overrides.refresh();
    voids.refresh();
    suspicious.refresh();
  };

  const refundRows = Array.isArray(refunds.data?.rows) ? refunds.data.rows : [];
  const overrideRows = Array.isArray(overrides.data?.rows) ? overrides.data.rows : [];
  const voidRows = Array.isArray(voids.data?.rows) ? voids.data.rows : [];
  const noSaleOpens = Array.isArray(suspicious.data?.no_sale_opens) ? suspicious.data.no_sale_opens : [];
  const failedAuthAttempts = Array.isArray(suspicious.data?.failed_auth_attempts) ? suspicious.data.failed_auth_attempts : [];
  const highVoidUsers = Array.isArray(suspicious.data?.high_void_users) ? suspicious.data.high_void_users : [];
  const cashVariances = Array.isArray(suspicious.data?.cash_variances) ? suspicious.data.cash_variances : [];

  const suspiciousItems: SuspiciousActivityItem[] = [
    ...(noSaleOpens.map((r) => ({
      category: 'NO_SALE_DRAWER',
      description: `${r.username ?? 'Unknown user'} opened drawer without a sale`,
      count: Number(r.count ?? 0),
      user_id: r.user_id ?? null,
      username: r.username ?? null,
      details: `No-sale opens: ${Number(r.count ?? 0)}`,
    }))),
    ...(failedAuthAttempts.map((r) => ({
      category: 'FAILED_AUTH',
      description: `Failed login attempts detected for user #${r.user_id ?? 'unknown'}`,
      count: Number(r.count ?? 0),
      user_id: r.user_id ?? null,
      username: null,
      details: `Failed attempts: ${Number(r.count ?? 0)}`,
    }))),
    ...(highVoidUsers.map((r) => ({
      category: 'HIGH_VOIDS',
      description: `${r.username ?? 'Unknown user'} has an elevated void count`,
      count: Number(r.void_count ?? 0),
      user_id: r.user_id ?? null,
      username: r.username ?? null,
      details: `Voids in period: ${Number(r.void_count ?? 0)}`,
    }))),
    ...(cashVariances.map((r) => ({
      category: 'CASH_VARIANCE',
      description: `${r.username ?? 'Unknown user'} closed with high register variance`,
      count: 1,
      user_id: r.user_id ?? null,
      username: r.username ?? null,
      details: `${r.register_name ?? 'Register'} variance ${safeMoney(Number(r.variance_cents ?? 0))}${r.closed_at ? ` at ${safeDate(r.closed_at)}` : ''}`,
    }))),
  ];

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
      {suspiciousItems.length > 0 && (
        <Card>
          <CardTitle>Suspicious Activity Flags</CardTitle>
          <div className="mt-4 flex flex-col gap-3">
            {suspiciousItems.map((item, i) => (
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
            <CardDescription>{refundRows.length} refunds</CardDescription>
          </div>
          {refundRows.length > 0 && (
            <Button variant="ghost" onClick={() => exportToCsv(
              [
                { key: 'document_number', header: 'Doc #' },
                { key: 'username', header: 'Employee' },
                { key: 'refund_amount_cents', header: 'Amount (cents)' },
                { key: 'reason', header: 'Reason' },
                { key: 'created_at', header: 'Date' },
              ],
              refundRows,
              'refund-audit',
            )}>Export CSV</Button>
          )}
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'document_number', header: 'Doc #', render: (r) => <span className="font-mono text-xs">{r.document_number ?? '-'}</span> },
              { key: 'username', header: 'Employee', render: (r) => <span>{(r as any).username ?? (r as any).created_by_username ?? '-'}</span> },
              { key: 'refund_amount_cents', header: 'Amount', render: (r) => <span className="tabular-nums text-red-600">{safeMoney(r.refund_amount_cents)}</span> },
              { key: 'reason', header: 'Reason', render: (r) => <span className="text-muted text-xs">{r.reason ?? '-'}</span> },
              { key: 'created_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{safeDate((r as any).created_at ?? (r as any).completed_at)}</span> },
            ]}
            data={refundRows}
            emptyMessage="No refunds for selected period."
          />
        </div>
      </Card>

      {/* Price Overrides */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Price Overrides</CardTitle>
          <CardDescription>{overrideRows.length} overrides</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'sale_document_number', header: 'Sale #', render: (r) => <span className="font-mono text-xs">{r.sale_document_number}</span> },
              { key: 'product_name', header: 'Product' },
              { key: 'original_price_cents', header: 'Original', render: (r) => <span className="tabular-nums">{safeMoney(r.original_price_cents)}</span> },
              { key: 'unit_price_cents', header: 'Sold At', render: (r) => <span className="tabular-nums">{safeMoney(r.unit_price_cents)}</span> },
              { key: 'discount_cents', header: 'Discount', render: (r) => <span className="tabular-nums text-amber-600">{safeMoney(r.discount_cents)}</span> },
              { key: 'username', header: 'By', render: (r) => <span>{(r as any).username ?? (r as any).cashier_username ?? (r as any).cashier_user_id ?? '-'}</span> },
              { key: 'approved_by_username', header: 'Approved By', render: (r) => <span className="text-muted">{r.approved_by_username ?? '-'}</span> },
              { key: 'created_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{safeDate((r as any).created_at ?? (r as any).sale_time)}</span> },
            ]}
            data={overrideRows}
            emptyMessage="No price overrides for selected period."
          />
        </div>
      </Card>

      {/* Void Audit */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Void Report</CardTitle>
          <CardDescription>{voidRows.length} voided transactions</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'document_number', header: 'Doc #', render: (r) => <span className="font-mono text-xs">{r.document_number}</span> },
              { key: 'original_amount_cents', header: 'Amount', render: (r) => <span className="tabular-nums">{safeMoney((r as any).original_amount_cents ?? (r as any).total_due_cents)}</span> },
              { key: 'voided_by_username', header: 'Voided By' },
              { key: 'void_reason', header: 'Reason', render: (r) => <span className="text-muted text-xs">{r.void_reason ?? '-'}</span> },
              { key: 'voided_at', header: 'Date', render: (r) => <span className="text-muted text-xs">{safeDate(r.voided_at)}</span> },
            ]}
            data={voidRows}
            emptyMessage="No voided transactions for selected period."
          />
        </div>
      </Card>
    </div>
  );
}
