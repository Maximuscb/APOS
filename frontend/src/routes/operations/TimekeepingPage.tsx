import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type TimeEntry = {
  id: number;
  user_id: number;
  store_id: number;
  clock_in_at: string;
  clock_out_at: string | null;
  status: string;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function TimekeepingPage() {
  const { currentStoreId: storeId } = useStore();
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadEntries = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ entries: TimeEntry[] }>(
        `/api/timekeeping/entries?store_id=${storeId}`,
      );
      setEntries(res.entries ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load time entries.');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  function statusVariant(status: string) {
    switch (status.toLowerCase()) {
      case 'clocked_in':
      case 'active':
        return 'success' as const;
      case 'clocked_out':
      case 'completed':
        return 'muted' as const;
      case 'pending':
        return 'warning' as const;
      default:
        return 'default' as const;
    }
  }

  const columns = [
    {
      key: 'id',
      header: 'ID',
      render: (entry: TimeEntry) => (
        <span className="tabular-nums">{entry.id}</span>
      ),
    },
    {
      key: 'user_id',
      header: 'User',
      render: (entry: TimeEntry) => (
        <span className="tabular-nums">{entry.user_id}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (entry: TimeEntry) => (
        <Badge variant={statusVariant(entry.status)}>{entry.status}</Badge>
      ),
    },
    {
      key: 'clock_in_at',
      header: 'Clock In',
      render: (entry: TimeEntry) => (
        <span className="text-muted">{formatDateTime(entry.clock_in_at)}</span>
      ),
    },
    {
      key: 'clock_out_at',
      header: 'Clock Out',
      render: (entry: TimeEntry) => (
        <span className="text-muted">
          {entry.clock_out_at ? formatDateTime(entry.clock_out_at) : '-'}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Timekeeping</h1>
          <p className="text-sm text-muted mt-1">
            Review and manage employee time entries.
          </p>
        </div>
        <Button variant="secondary" onClick={loadEntries} disabled={loading}>
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Time Entries</CardTitle>
        </div>
        <div className="mt-4">
          {loading ? (
            <div className="px-5 pb-5 text-sm text-muted">Loading time entries...</div>
          ) : (
            <DataTable
              columns={columns}
              data={entries}
              emptyMessage="No time entries found for this store."
            />
          )}
        </div>
      </Card>
    </div>
  );
}
