import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
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
      loadRegisters();
    } catch {
      // silent
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
  return (
    <Card>
      <CardTitle>Cash Drawers</CardTitle>
      <p className="text-sm text-muted mt-2">
        Coming soon. Cash drawer management will be available in a future update.
      </p>
    </Card>
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
