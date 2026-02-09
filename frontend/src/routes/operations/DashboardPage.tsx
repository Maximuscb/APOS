import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney } from '@/lib/format';

interface DashboardSummary {
  sales_today: number;
  sales_total_cents: number;
  open_registers: number;
  pending_tasks: number;
}

export function DashboardPage() {
  const { currentStoreId } = useStore();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentStoreId) return;
    setLoading(true);
    api.get<DashboardSummary>(`/api/analytics/dashboard-summary?store_id=${currentStoreId}`)
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [currentStoreId]);

  if (loading) {
    return <div className="p-6 text-muted">Loading dashboard...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5">
          <p className="text-sm font-medium text-muted">Sales Today</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">{summary?.sales_today ?? 0}</p>
        </Card>

        <Card className="p-5">
          <p className="text-sm font-medium text-muted">Revenue Today</p>
          <p className="text-3xl font-bold text-emerald-700 mt-1">
            {formatMoney(summary?.sales_total_cents ?? 0)}
          </p>
        </Card>

        <Card className="p-5">
          <p className="text-sm font-medium text-muted">Open Registers</p>
          <p className="text-3xl font-bold text-blue-700 mt-1">{summary?.open_registers ?? 0}</p>
        </Card>

        <Card className="p-5">
          <p className="text-sm font-medium text-muted">Pending Tasks</p>
          <p className="text-3xl font-bold text-amber-700 mt-1">{summary?.pending_tasks ?? 0}</p>
        </Card>
      </div>
    </div>
  );
}
