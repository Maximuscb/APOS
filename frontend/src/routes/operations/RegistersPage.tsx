import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney, formatDateTime } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type Register = {
  id: number;
  store_id: number;
  register_number: number;
  name: string;
  location: string | null;
  device_id: string | null;
  is_active: boolean;
};

type RegisterSession = {
  id: number;
  register_id: number;
  user_id: number;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash_cents: number;
  closing_cash_cents: number | null;
  variance_cents: number | null;
};

type DrawerEvent = {
  id: number;
  register_id: number;
  register_session_id: number;
  event_type: string;
  amount_cents: number | null;
  reason: string | null;
  occurred_at: string;
};

type RegisterDetail = Register & {
  current_session: RegisterSession | null;
};

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function RegistersPage() {
  const { currentStoreId: storeId } = useStore();

  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Selected register detail
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RegisterDetail | null>(null);
  const [sessions, setSessions] = useState<RegisterSession[]>([]);
  const [events, setEvents] = useState<DrawerEvent[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  /* ---- Load register list ---- */

  const loadRegisters = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ registers: Register[] }>(
        `/api/registers?store_id=${storeId}`,
      );
      setRegisters(res.registers ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load registers.');
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    loadRegisters();
    setSelectedId(null);
    setDetail(null);
  }, [loadRegisters]);

  /* ---- Load register detail ---- */

  const loadDetail = useCallback(async (registerId: number) => {
    setDetailLoading(true);
    try {
      const [regDetail, sessionsRes, eventsRes] = await Promise.all([
        api.get<RegisterDetail>(`/api/registers/${registerId}`),
        api.get<{ sessions: RegisterSession[] }>(
          `/api/registers/${registerId}/sessions?limit=20`,
        ),
        api.get<{ events: DrawerEvent[] }>(
          `/api/registers/${registerId}/events?limit=50`,
        ),
      ]);
      setDetail(regDetail);
      setSessions(sessionsRes.sessions ?? []);
      setEvents(eventsRes.events ?? []);
    } catch {
      setDetail(null);
      setSessions([]);
      setEvents([]);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId != null) {
      loadDetail(selectedId);
    }
  }, [selectedId, loadDetail]);

  /* ---- Register list columns ---- */

  const registerColumns = [
    {
      key: 'register_number',
      header: '#',
      render: (row: Register) => (
        <span className="font-medium tabular-nums">{row.register_number}</span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      render: (row: Register) => <span>{row.name}</span>,
    },
    {
      key: 'location',
      header: 'Location',
      render: (row: Register) => (
        <span className="text-slate-500">{row.location ?? '-'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: Register) => (
        <Badge variant={row.is_active ? 'success' : 'muted'}>
          {row.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
  ];

  /* ---- Session columns ---- */

  const sessionColumns = [
    {
      key: 'status',
      header: 'Status',
      render: (row: RegisterSession) => (
        <Badge variant={row.status === 'OPEN' ? 'primary' : row.status === 'CLOSED' ? 'muted' : 'warning'}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'opened_at',
      header: 'Opened',
      render: (row: RegisterSession) => (
        <span className="text-sm">{formatDateTime(row.opened_at)}</span>
      ),
    },
    {
      key: 'closed_at',
      header: 'Closed',
      render: (row: RegisterSession) => (
        <span className="text-sm text-slate-500">
          {row.closed_at ? formatDateTime(row.closed_at) : '-'}
        </span>
      ),
    },
    {
      key: 'opening_cash',
      header: 'Opening Cash',
      className: 'text-right',
      render: (row: RegisterSession) => (
        <span className="tabular-nums">{formatMoney(row.opening_cash_cents)}</span>
      ),
    },
    {
      key: 'closing_cash',
      header: 'Closing Cash',
      className: 'text-right',
      render: (row: RegisterSession) => (
        <span className="tabular-nums">
          {row.closing_cash_cents != null ? formatMoney(row.closing_cash_cents) : '-'}
        </span>
      ),
    },
    {
      key: 'variance',
      header: 'Variance',
      className: 'text-right',
      render: (row: RegisterSession) => {
        if (row.variance_cents == null) return <span className="text-slate-500">-</span>;
        const isNeg = row.variance_cents < 0;
        const isPos = row.variance_cents > 0;
        return (
          <span
            className={`tabular-nums font-medium ${
              isNeg ? 'text-red-600' : isPos ? 'text-emerald-600' : ''
            }`}
          >
            {isPos ? '+' : ''}
            {formatMoney(row.variance_cents)}
          </span>
        );
      },
    },
  ];

  /* ---- Drawer event columns ---- */

  const eventColumns = [
    {
      key: 'event_type',
      header: 'Event',
      render: (row: DrawerEvent) => (
        <Badge
          variant={
            row.event_type === 'CASH_IN'
              ? 'success'
              : row.event_type === 'CASH_OUT'
                ? 'danger'
                : 'default'
          }
        >
          {row.event_type}
        </Badge>
      ),
    },
    {
      key: 'session',
      header: 'Session',
      render: (row: DrawerEvent) => (
        <span className="tabular-nums text-slate-500">#{row.register_session_id}</span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      className: 'text-right',
      render: (row: DrawerEvent) => (
        <span className="tabular-nums">
          {row.amount_cents != null ? formatMoney(row.amount_cents) : '-'}
        </span>
      ),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (row: DrawerEvent) => (
        <span className="text-slate-500">{row.reason ?? '-'}</span>
      ),
    },
    {
      key: 'occurred_at',
      header: 'Time',
      render: (row: DrawerEvent) => (
        <span className="text-sm">{formatDateTime(row.occurred_at)}</span>
      ),
    },
  ];

  /* ---- Render ---- */

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Registers</h1>
        <p className="text-sm text-muted mt-1">
          View register status, session history, and drawer events.
        </p>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Register list */}
      {loading ? (
        <p className="text-sm text-muted">Loading registers...</p>
      ) : (
        <DataTable
          columns={registerColumns}
          data={registers}
          onRowClick={(row) => setSelectedId(row.id)}
          emptyMessage="No registers found for this store."
        />
      )}

      {/* Selected register detail */}
      {selectedId != null && (
        <>
          {detailLoading ? (
            <p className="text-sm text-muted">Loading register details...</p>
          ) : detail ? (
            <>
              {/* Register info card */}
              <Card>
                <CardTitle>{detail.name}</CardTitle>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Register #</p>
                    <p className="text-sm text-slate-900 mt-0.5">{detail.register_number}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Location</p>
                    <p className="text-sm text-slate-900 mt-0.5">{detail.location ?? '-'}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Device ID</p>
                    <p className="text-sm text-slate-900 mt-0.5 font-mono text-xs">{detail.device_id ?? '-'}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Status</p>
                    <div className="mt-0.5">
                      <Badge variant={detail.is_active ? 'success' : 'muted'}>
                        {detail.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Current session */}
                {detail.current_session && (
                  <div className="mt-4 p-3 rounded-xl bg-blue-50 border border-blue-200">
                    <p className="text-sm font-medium text-blue-800">
                      Current Session #{detail.current_session.id}
                    </p>
                    <p className="text-xs text-blue-700 mt-1">
                      Status: {detail.current_session.status} &middot; Opened: {formatDateTime(detail.current_session.opened_at)} &middot; Opening Cash: {formatMoney(detail.current_session.opening_cash_cents)}
                    </p>
                  </div>
                )}
              </Card>

              {/* Session history */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold text-slate-900">Session History</h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => loadDetail(selectedId!)}
                  >
                    Refresh
                  </Button>
                </div>
                <DataTable
                  columns={sessionColumns}
                  data={sessions}
                  emptyMessage="No sessions found."
                />
              </div>

              {/* Drawer events */}
              <div>
                <h2 className="text-lg font-semibold text-slate-900 mb-3">Drawer Events</h2>
                <DataTable
                  columns={eventColumns}
                  data={events}
                  emptyMessage="No drawer events found."
                />
              </div>
            </>
          ) : (
            <p className="text-sm text-muted">Failed to load register details.</p>
          )}
        </>
      )}
    </div>
  );
}
