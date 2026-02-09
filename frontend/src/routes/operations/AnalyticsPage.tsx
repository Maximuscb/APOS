import { useMemo, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';

const REPORTS = [
  { key: 'sales-trends', label: 'Sales Trends', description: 'Revenue and transaction trends over time.' },
  { key: 'inventory-valuation', label: 'Inventory Valuation', description: 'Current inventory value at cost.' },
  { key: 'margin-cogs', label: 'Margin / COGS', description: 'Gross margin and cost analysis.' },
  { key: 'slow-stock', label: 'Slow & Dead Stock', description: 'Products with low movement.' },
  { key: 'cashier-performance', label: 'Cashier Performance', description: 'Sales metrics by cashier.' },
  { key: 'register-performance', label: 'Register Performance', description: 'Sales metrics by register.' },
];

type ChartPoint = { label: string; value: number };

function extractPoints(payload: unknown): ChartPoint[] {
  if (!payload || typeof payload !== 'object') return [];
  const obj = payload as Record<string, unknown>;

  if (Array.isArray(obj.items)) {
    const points = (obj.items as unknown[])
      .map((x, i) => {
        if (!x || typeof x !== 'object') return null;
        const row = x as Record<string, unknown>;
        const label = String(row.label ?? row.name ?? row.date ?? row.id ?? `#${i + 1}`);
        const raw = row.value ?? row.amount ?? row.total ?? row.count ?? row.metric;
        const value = Number(raw);
        return Number.isFinite(value) ? { label, value } : null;
      })
      .filter((p): p is ChartPoint => !!p);
    if (points.length > 0) return points.slice(0, 16);
  }

  const pairs = Object.entries(obj)
    .map(([k, v]) => {
      const n = Number(v);
      return Number.isFinite(n) ? { label: k, value: n } : null;
    })
    .filter((p): p is ChartPoint => !!p);
  return pairs.slice(0, 16);
}

function BarChart({ points }: { points: ChartPoint[] }) {
  const max = Math.max(...points.map((p) => p.value), 1);
  return (
    <div className="space-y-2">
      {points.map((p) => (
        <div key={p.label} className="grid grid-cols-[140px_1fr_80px] items-center gap-2 text-sm">
          <span className="truncate text-slate-600">{p.label}</span>
          <div className="h-3 rounded bg-slate-100 overflow-hidden">
            <div className="h-full bg-primary rounded" style={{ width: `${Math.max(2, (p.value / max) * 100)}%` }} />
          </div>
          <span className="text-right tabular-nums text-slate-700">{p.value.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const { currentStoreId: storeId } = useStore();
  const [activeReport, setActiveReport] = useState<string | null>(null);
  const [reportData, setReportData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function fetchReport(key: string) {
    setActiveReport(key);
    setLoading(true);
    setError('');
    setReportData(null);
    try {
      const data = await api.get<Record<string, unknown>>(`/api/analytics/${key}?store_id=${storeId}`);
      setReportData(data);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load report.');
    } finally {
      setLoading(false);
    }
  }

  const activeLabel = REPORTS.find((r) => r.key === activeReport)?.label ?? '';
  const points = useMemo(() => extractPoints(reportData), [reportData]);

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-sm text-muted mt-1">Interactive analytics for your current store.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map((report) => (
          <button
            key={report.key}
            onClick={() => fetchReport(report.key)}
            disabled={loading && activeReport === report.key}
            className={`text-left p-5 rounded-2xl border transition-all cursor-pointer ${
              activeReport === report.key ? 'border-primary bg-primary-light shadow-sm' : 'border-border bg-surface hover:border-primary/40 hover:shadow-sm'
            } disabled:opacity-50 disabled:pointer-events-none`}
          >
            <h3 className="text-sm font-semibold text-slate-900">{report.label}</h3>
            <p className="text-xs text-muted mt-1">{report.description}</p>
          </button>
        ))}
      </div>

      {error && <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}

      {loading && <Card><div className="text-sm text-muted">Loading report...</div></Card>}

      {!loading && reportData && (
        <Card>
          <CardTitle>{activeLabel}</CardTitle>
          <CardDescription>Store #{storeId}</CardDescription>
          <div className="mt-4">
            {points.length > 0 ? (
              <BarChart points={points} />
            ) : (
              <p className="text-sm text-muted">No chartable numeric series in this report payload.</p>
            )}
          </div>
          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={() => activeReport && fetchReport(activeReport)}>
              Refresh
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
