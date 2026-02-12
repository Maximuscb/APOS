import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type TimeEntry = {
  id: number;
  user_id: number;
  username?: string;
  store_id: number;
  clock_in_at: string;
  clock_out_at: string | null;
  status: string;
  total_worked_minutes: number | null;
  total_break_minutes: number | null;
  notes: string | null;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Convert ISO string to datetime-local input value (local timezone). */
function toLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const offset = d.getTimezoneOffset();
  const local = new Date(d.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

function formatMinutes(mins: number | null): string {
  if (mins == null) return '-';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}h ${m}m`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function TimekeepingPage() {
  const { currentStoreId: storeId } = useStore();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission('MANAGE_TIMEKEEPING');

  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit dialog state
  const [editEntry, setEditEntry] = useState<TimeEntry | null>(null);
  const [editClockIn, setEditClockIn] = useState('');
  const [editClockOut, setEditClockOut] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editReason, setEditReason] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

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

  function openEdit(entry: TimeEntry) {
    setEditEntry(entry);
    setEditClockIn(toLocalInput(entry.clock_in_at));
    setEditClockOut(toLocalInput(entry.clock_out_at));
    setEditNotes(entry.notes ?? '');
    setEditReason('');
    setEditError('');
  }

  async function handleEdit() {
    if (!editEntry) return;
    if (!editReason.trim()) {
      setEditError('A reason is required for audit purposes.');
      return;
    }
    setEditBusy(true);
    setEditError('');
    try {
      const body: Record<string, unknown> = {
        reason: editReason.trim(),
      };
      if (editClockIn) body.clock_in_at = new Date(editClockIn).toISOString();
      if (editClockOut) body.clock_out_at = new Date(editClockOut).toISOString();
      body.notes = editNotes.trim() || null;

      await api.patch(`/api/timekeeping/entries/${editEntry.id}`, body);
      setEditEntry(null);
      loadEntries();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Update failed.');
    } finally {
      setEditBusy(false);
    }
  }

  function statusVariant(status: string) {
    switch (status.toLowerCase()) {
      case 'open':
        return 'success' as const;
      case 'closed':
        return 'muted' as const;
      default:
        return 'default' as const;
    }
  }

  const columns = [
    {
      key: 'username',
      header: 'User',
      render: (entry: TimeEntry) => (
        <span className="font-medium">{entry.username ?? `#${entry.user_id}`}</span>
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
        <span className="text-muted tabular-nums">{formatDateTime(entry.clock_in_at)}</span>
      ),
    },
    {
      key: 'clock_out_at',
      header: 'Clock Out',
      render: (entry: TimeEntry) => (
        <span className="text-muted tabular-nums">
          {entry.clock_out_at ? formatDateTime(entry.clock_out_at) : '-'}
        </span>
      ),
    },
    {
      key: 'total_worked_minutes',
      header: 'Worked',
      render: (entry: TimeEntry) => (
        <span className="text-muted tabular-nums">{formatMinutes(entry.total_worked_minutes)}</span>
      ),
    },
    {
      key: 'notes',
      header: 'Notes',
      render: (entry: TimeEntry) => (
        <span className="text-muted text-xs truncate max-w-[200px] block">
          {entry.notes || '-'}
        </span>
      ),
    },
    ...(canEdit
      ? [
          {
            key: 'actions',
            header: '',
            render: (entry: TimeEntry) => (
              <Button variant="ghost" size="sm" onClick={() => openEdit(entry)}>
                Edit
              </Button>
            ),
          },
        ]
      : []),
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

      {/* Edit Dialog */}
      <Dialog open={!!editEntry} onClose={() => setEditEntry(null)} title="Edit Time Entry">
        {editError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {editError}
          </div>
        )}
        <div className="flex flex-col gap-4">
          <div className="text-sm text-muted">
            Editing entry for <span className="font-medium text-slate-900">{editEntry?.username ?? `#${editEntry?.user_id}`}</span>
          </div>
          <Input
            label="Clock In"
            type="datetime-local"
            value={editClockIn}
            onChange={(e) => setEditClockIn(e.target.value)}
          />
          <Input
            label="Clock Out"
            type="datetime-local"
            value={editClockOut}
            onChange={(e) => setEditClockOut(e.target.value)}
          />
          <Input
            label="Notes"
            value={editNotes}
            onChange={(e) => setEditNotes(e.target.value)}
            placeholder="Optional"
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="edit-reason" className="text-sm font-medium text-slate-700">
              Reason for edit <span className="text-red-500">*</span>
            </label>
            <textarea
              id="edit-reason"
              value={editReason}
              onChange={(e) => setEditReason(e.target.value)}
              placeholder="Why is this entry being changed?"
              rows={2}
              className="px-3 py-2 rounded-xl border border-border bg-white text-sm
                placeholder:text-slate-400 focus:outline-2 focus:outline-primary focus:border-primary
                transition-colors resize-none"
            />
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleEdit} disabled={editBusy}>
            {editBusy ? 'Saving...' : 'Save'}
          </Button>
          <Button variant="secondary" onClick={() => setEditEntry(null)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
