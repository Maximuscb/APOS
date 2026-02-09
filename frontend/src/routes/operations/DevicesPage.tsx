import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney, formatDateTime } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Dialog } from '@/components/ui/Dialog';
import { Tabs } from '@/components/ui/Tabs';
import { Input } from '@/components/ui/Input';

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
  current_session: {
    id: number;
    status: string;
    user_id: number;
    opened_at: string;
  } | null;
};

type DrawerEvent = {
  id: number;
  event_type: string;
  amount_cents: number | null;
  reason: string | null;
  occurred_at: string;
  user_id: number;
};

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function DevicesPage() {
  const [activeTab, setActiveTab] = useState('Registers');

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Devices</h1>
        <p className="text-sm text-muted mt-1">
          Manage registers, cash drawers, and printers.
        </p>
      </div>

      <Tabs
        tabs={['Registers', 'Cash Drawers', 'Printers']}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'Registers' && <RegistersTab />}
      {activeTab === 'Cash Drawers' && <DrawersTab />}
      {activeTab === 'Printers' && <PrintersTab />}
    </div>
  );
}

/* ================================================================== */
/*  REGISTERS TAB                                                      */
/* ================================================================== */

function RegistersTab() {
  const { currentStoreId: storeId } = useStore();

  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newNumber, setNewNumber] = useState('');
  const [newName, setNewName] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newDeviceId, setNewDeviceId] = useState('');
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');

  // Edit dialog
  const [editRegister, setEditRegister] = useState<Register | null>(null);
  const [editName, setEditName] = useState('');
  const [editLocation, setEditLocation] = useState('');
  const [editDeviceId, setEditDeviceId] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

  /* ---- Load registers ---- */

  const loadRegisters = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ registers: Register[] }>(
        `/api/registers/?store_id=${storeId}`,
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
  }, [loadRegisters]);

  /* ---- Create register ---- */

  async function handleCreate() {
    if (!newName.trim()) {
      setCreateError('Name is required.');
      return;
    }
    const regNum = parseInt(newNumber, 10);
    if (Number.isNaN(regNum) || regNum <= 0) {
      setCreateError('Register number must be a positive integer.');
      return;
    }

    setCreateBusy(true);
    setCreateError('');
    try {
      const body: Record<string, unknown> = {
        store_id: storeId,
        register_number: regNum,
        name: newName.trim(),
      };
      if (newLocation.trim()) body.location = newLocation.trim();
      if (newDeviceId.trim()) body.device_id = newDeviceId.trim();

      await api.post('/api/registers/', body);
      setNewNumber('');
      setNewName('');
      setNewLocation('');
      setNewDeviceId('');
      setShowCreate(false);
      loadRegisters();
    } catch (err: any) {
      setCreateError(err?.detail ?? err?.message ?? 'Failed to create register.');
    } finally {
      setCreateBusy(false);
    }
  }

  /* ---- Edit register ---- */

  function openEdit(reg: Register) {
    setEditRegister(reg);
    setEditName(reg.name);
    setEditLocation(reg.location ?? '');
    setEditDeviceId(reg.device_id ?? '');
    setEditError('');
  }

  async function handleEdit() {
    if (!editRegister) return;
    setEditBusy(true);
    setEditError('');
    try {
      const body: Record<string, unknown> = {
        name: editName.trim(),
        location: editLocation.trim() || null,
        device_id: editDeviceId.trim() || null,
      };
      await api.patch(`/api/registers/${editRegister.id}`, body);
      setEditRegister(null);
      loadRegisters();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Update failed.');
    } finally {
      setEditBusy(false);
    }
  }

  /* ---- Toggle active ---- */

  async function toggleActive(reg: Register) {
    try {
      await api.patch(`/api/registers/${reg.id}`, {
        is_active: !reg.is_active,
      });
      setSuccess(`Register ${reg.register_number} ${reg.is_active ? 'deactivated' : 'activated'}.`);
      loadRegisters();
    } catch {
      // silent
    }
  }

  async function forceClose(reg: Register) {
    const val = window.prompt('Closing cash in dollars (leave blank for expected cash):', '');
    if (val === null) return;
    const body: Record<string, unknown> = {};
    if (val.trim() !== '') {
      const dollars = Number(val);
      if (!Number.isFinite(dollars) || dollars < 0) {
        setError('Invalid closing cash amount.');
        return;
      }
      body.closing_cash_cents = Math.round(dollars * 100);
    }
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/registers/${reg.id}/force-close`, body);
      setSuccess(`Forced register close completed for ${reg.register_number}.`);
      loadRegisters();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to force close register.');
    }
  }

  /* ---- Table columns ---- */

  const columns = [
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
      key: 'device_id',
      header: 'Device ID',
      render: (row: Register) => (
        <span className="font-mono text-xs text-slate-500">
          {row.device_id ?? '-'}
        </span>
      ),
    },
    {
      key: 'session',
      header: 'Session',
      render: (row: Register) => (
        row.current_session
          ? <Badge variant="success">Open</Badge>
          : <Badge variant="muted">No session</Badge>
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
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row: Register) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
            Edit
          </Button>
          {row.current_session && (
            <Button variant="danger" size="sm" onClick={() => forceClose(row)}>
              Force Close
            </Button>
          )}
          <Button
            variant={row.is_active ? 'warning' : 'secondary'}
            size="sm"
            onClick={() => toggleActive(row)}
          >
            {row.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        </div>
      ),
    },
  ];

  /* ---- Render ---- */

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={() => setShowCreate(true)}>Add Register</Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted">Loading registers...</p>
      ) : (
        <DataTable
          columns={columns}
          data={registers}
          emptyMessage="No registers found for this store."
        />
      )}

      {/* Create Register Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Add Register">
        {createError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {createError}
          </div>
        )}
        <div className="flex flex-col gap-4">
          <Input
            label="Register Number"
            type="number"
            min="1"
            value={newNumber}
            onChange={(e) => setNewNumber(e.target.value)}
            placeholder="e.g. 1"
          />
          <Input
            label="Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. Front Counter"
          />
          <Input
            label="Location"
            value={newLocation}
            onChange={(e) => setNewLocation(e.target.value)}
            placeholder="Optional - e.g. Main floor"
          />
          <Input
            label="Device ID"
            value={newDeviceId}
            onChange={(e) => setNewDeviceId(e.target.value)}
            placeholder="Optional - hardware identifier"
          />
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>
            {createBusy ? 'Creating...' : 'Create'}
          </Button>
          <Button variant="secondary" onClick={() => setShowCreate(false)}>
            Cancel
          </Button>
        </div>
      </Dialog>

      {/* Edit Register Dialog */}
      <Dialog open={!!editRegister} onClose={() => setEditRegister(null)} title="Edit Register">
        {editError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {editError}
          </div>
        )}
        <div className="flex flex-col gap-4">
          <Input
            label="Name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
          <Input
            label="Location"
            value={editLocation}
            onChange={(e) => setEditLocation(e.target.value)}
            placeholder="Optional"
          />
          <Input
            label="Device ID"
            value={editDeviceId}
            onChange={(e) => setEditDeviceId(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleEdit} disabled={editBusy}>
            {editBusy ? 'Saving...' : 'Save'}
          </Button>
          <Button variant="secondary" onClick={() => setEditRegister(null)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/* ================================================================== */
/*  DRAWERS TAB (placeholder)                                          */
/* ================================================================== */

function DrawersTab() {
  const { currentStoreId: storeId } = useStore();
  const [registers, setRegisters] = useState<Register[]>([]);
  const [drawerEvents, setDrawerEvents] = useState<Record<number, DrawerEvent[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await api.get<{ registers: Register[] }>(
          `/api/registers/?store_id=${storeId}`,
        );
        const regs = res.registers ?? [];
        setRegisters(regs);

        const eventMap: Record<number, DrawerEvent[]> = {};
        await Promise.allSettled(
          regs
            .filter((r) => r.current_session)
            .map(async (r) => {
              const ev = await api.get<{ events: DrawerEvent[] }>(
                `/api/registers/${r.id}/events?limit=5`,
              );
              eventMap[r.id] = ev.events ?? [];
            }),
        );
        setDrawerEvents(eventMap);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [storeId]);

  if (loading) {
    return <p className="text-sm text-muted">Loading drawer status...</p>;
  }

  const activeRegisters = registers.filter((r) => r.current_session);
  const inactiveRegisters = registers.filter((r) => !r.current_session);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle>Active Drawers</CardTitle>
        <p className="text-sm text-muted mt-1">
          Registers with open sessions and their current drawer activity.
        </p>

        {activeRegisters.length === 0 ? (
          <p className="text-sm text-muted mt-4">No registers have an open session.</p>
        ) : (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 pr-4 font-medium">#</th>
                  <th className="py-2 pr-4 font-medium">Register</th>
                  <th className="py-2 pr-4 font-medium">Session</th>
                  <th className="py-2 pr-4 font-medium">Last Event</th>
                  <th className="py-2 pr-4 font-medium">Amount</th>
                  <th className="py-2 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {activeRegisters.map((reg) => {
                  const events = drawerEvents[reg.id] ?? [];
                  const lastEvent = events[0] ?? null;
                  return (
                    <tr key={reg.id} className="border-b border-border/50">
                      <td className="py-2.5 pr-4 font-medium tabular-nums">
                        {reg.register_number}
                      </td>
                      <td className="py-2.5 pr-4">{reg.name}</td>
                      <td className="py-2.5 pr-4">
                        <Badge variant="success">Open</Badge>
                      </td>
                      <td className="py-2.5 pr-4">
                        {lastEvent ? (
                          <Badge
                            variant={
                              lastEvent.event_type === 'NO_SALE'
                                ? 'warning'
                                : lastEvent.event_type === 'CASH_DROP'
                                  ? 'default'
                                  : 'muted'
                            }
                          >
                            {lastEvent.event_type}
                          </Badge>
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4 tabular-nums">
                        {lastEvent?.amount_cents != null
                          ? formatMoney(lastEvent.amount_cents)
                          : '-'}
                      </td>
                      <td className="py-2.5 text-muted">
                        {lastEvent ? formatDateTime(lastEvent.occurred_at) : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {inactiveRegisters.length > 0 && (
        <Card>
          <CardTitle>Inactive Drawers</CardTitle>
          <p className="text-sm text-muted mt-1">
            Registers without an open session.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {inactiveRegisters.map((reg) => (
              <div
                key={reg.id}
                className="px-3 py-2 rounded-xl border border-border bg-slate-50 text-sm text-slate-500"
              >
                {reg.register_number} — {reg.name}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ================================================================== */
/*  PRINTERS TAB (placeholder)                                         */
/* ================================================================== */

function PrintersTab() {
  return (
    <Card>
      <CardTitle>Printers</CardTitle>
      <p className="text-sm text-muted mt-2">
        Coming soon. Printer configuration and management will be available in a future update.
      </p>
    </Card>
  );
}
