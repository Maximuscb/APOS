import { useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';

/* ------------------------------------------------------------------ */
/*  Report definitions                                                 */
/* ------------------------------------------------------------------ */

const REPORTS = [
  { key: 'sales-trends', label: 'Sales Trends', description: 'Revenue and transaction trends over time.' },
  { key: 'inventory-valuation', label: 'Inventory Valuation', description: 'Current inventory value at cost.' },
  { key: 'margin-cogs', label: 'Margin / COGS', description: 'Gross margin and cost of goods sold analysis.' },
  { key: 'slow-stock', label: 'Slow & Dead Stock', description: 'Products with low or no recent movement.' },
  { key: 'cashier-performance', label: 'Cashier Performance', description: 'Sales metrics by cashier.' },
  { key: 'register-performance', label: 'Register Performance', description: 'Sales metrics by register.' },
];

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

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

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-sm text-muted mt-1">
          Quick analytics reports for your store.
        </p>
      </div>

      {/* Report Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map((report) => (
          <button
            key={report.key}
            onClick={() => fetchReport(report.key)}
            disabled={loading && activeReport === report.key}
            className={`text-left p-5 rounded-2xl border transition-all cursor-pointer
              ${activeReport === report.key
                ? 'border-primary bg-primary-light shadow-sm'
                : 'border-border bg-surface hover:border-primary/40 hover:shadow-sm'
              }
              disabled:opacity-50 disabled:pointer-events-none`}
          >
            <h3 className="text-sm font-semibold text-slate-900">{report.label}</h3>
            <p className="text-xs text-muted mt-1">{report.description}</p>
          </button>
        ))}
      </div>

      {/* Error */}
      {error ? (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      {/* Report Output */}
      {loading && (
        <Card>
          <div className="text-sm text-muted">Loading report...</div>
        </Card>
      )}

      {!loading && reportData && (
        <Card>
          <CardTitle>{activeLabel}</CardTitle>
          <CardDescription>Report data for Store #{storeId}.</CardDescription>
          <div className="mt-4 overflow-x-auto">
            <pre className="rounded-xl bg-slate-50 border border-border p-4 text-xs text-slate-700 whitespace-pre-wrap break-words">
              <code>{JSON.stringify(reportData, null, 2)}</code>
            </pre>
          </div>
          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={() => fetchReport(activeReport!)}>
              Refresh
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
