import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
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
  register_number: number | string;
  name: string;
  location: string | null;
  is_active: boolean;
  current_session: {
    id: number;
    status: string;
    user_id: number;
    opened_at: string;
  } | null;
};

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function DevicesPage() {
  const [activeTab, setActiveTab] = useState('Registers');
  const { hasPermission } = useAuth();
  const { currentStoreId, setStoreId, stores } = useStore();
  const canSwitchStore = hasPermission('SWITCH_STORE') && hasPermission('MANAGE_REGISTER') && stores.length > 1;
  const tabs = ['Registers', 'Cash Drawers', 'Printers'];

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Devices</h1>
          <p className="text-sm text-muted mt-1">
            Manage registers, cash drawers, and printers.
          </p>
        </div>
        {canSwitchStore && (
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-slate-700">Store:</label>
            <select
              value={String(currentStoreId)}
              onChange={(e) => setStoreId(Number(e.target.value))}
              className="h-9 rounded-xl border border-border bg-white px-3 text-sm"
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <Tabs
        tabs={tabs}
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
  const { hasPermission } = useAuth();
  const canManageRegisters = hasPermission('MANAGE_REGISTER');
  const { currentStoreId: storeId, stores } = useStore();

  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newStoreId, setNewStoreId] = useState<number>(storeId);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');

  // Edit dialog
  const [editRegister, setEditRegister] = useState<Register | null>(null);
  const [editName, setEditName] = useState('');
  const [editLocation, setEditLocation] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

  function normalizeCreateError(err: any) {
    const message = err?.detail ?? err?.message ?? 'Failed to create register.';
    const lower = String(message).toLowerCase();
    if (
      lower.includes('store_id, register_number, and name required') ||
      lower.includes('tore_id, register_number, and name required')
    ) {
      return 'Store and name are required.';
    }
    return message;
  }

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

  useEffect(() => {
    setNewStoreId(storeId);
  }, [storeId]);

  /* ---- Create register ---- */

  async function handleCreate() {
    if (!newName.trim()) {
      setCreateError('Name is required.');
      return;
    }

    setCreateBusy(true);
    setCreateError('');
    try {
      const body: Record<string, unknown> = {
        store_id: newStoreId,
        name: newName.trim(),
      };
      if (newLocation.trim()) body.location = newLocation.trim();

      await api.post('/api/registers/', body);
      setNewName('');
      setNewLocation('');
      setNewStoreId(storeId);
      setShowCreate(false);
      loadRegisters();
    } catch (err: any) {
      setCreateError(normalizeCreateError(err));
    } finally {
      setCreateBusy(false);
    }
  }

  /* ---- Edit register ---- */

  function openEdit(reg: Register) {
    setEditRegister(reg);
    setEditName(reg.name);
    setEditLocation(reg.location ?? '');
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
          {canManageRegisters ? (
            <>
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
            </>
          ) : (
            <span className="text-xs text-slate-400">View only</span>
          )}
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

      {canManageRegisters && (
        <div className="flex justify-end">
          <Button onClick={() => setShowCreate(true)}>Add Register</Button>
        </div>
      )}

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
      <Dialog open={showCreate && canManageRegisters} onClose={() => setShowCreate(false)} title="Add Register">
        {createError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {createError}
          </div>
        )}
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Store</label>
            <select
              value={String(newStoreId)}
              onChange={(e) => setNewStoreId(Number(e.target.value))}
              className="h-11 rounded-xl border border-border bg-white px-3 text-sm"
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
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
/*  DRAWERS TAB                                                        */
/* ================================================================== */

type CashDrawerData = {
  id: number;
  register_id: number;
  model: string | null;
  serial_number: string | null;
  connection_type: string | null;
  connection_address: string | null;
  is_active: boolean;
};

type DrawerRow = {
  register: Register;
  drawer: CashDrawerData;
};

const DRAWER_CONN_TYPES = ['USB', 'SERIAL', 'NETWORK', 'PRINTER_DRIVEN'] as const;

function DrawersTab() {
  const { hasPermission } = useAuth();
  const canManageRegisters = hasPermission('MANAGE_REGISTER');
  const { currentStoreId: storeId } = useStore();
  const [rows, setRows] = useState<DrawerRow[]>([]);
  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createRegId, setCreateRegId] = useState<number>(0);
  const [createModel, setCreateModel] = useState('');
  const [createSerial, setCreateSerial] = useState('');
  const [createConnType, setCreateConnType] = useState('');
  const [createConnAddr, setCreateConnAddr] = useState('');
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');

  // Edit dialog
  const [editRow, setEditRow] = useState<DrawerRow | null>(null);
  const [editModel, setEditModel] = useState('');
  const [editSerial, setEditSerial] = useState('');
  const [editConnType, setEditConnType] = useState('');
  const [editConnAddr, setEditConnAddr] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ registers: Register[] }>(
        `/api/registers/?store_id=${storeId}`,
      );
      const regs = res.registers ?? [];
      setRegisters(regs);

      const drawerResults = await Promise.allSettled(
        regs.map(async (r) => {
          const d = await api.get<{ cash_drawer: CashDrawerData | null }>(
            `/api/registers/${r.id}/cash-drawer`,
          );
          return { register: r, drawer: d.cash_drawer };
        }),
      );

      setRows(
        drawerResults
          .filter((r): r is PromiseFulfilledResult<{ register: Register; drawer: CashDrawerData | null }> => r.status === 'fulfilled')
          .map((r) => r.value)
          .filter((r): r is DrawerRow => r.drawer !== null),
      );
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load drawers.');
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => { load(); }, [load]);

  // Registers that don't already have a drawer
  const availableRegisters = registers.filter(
    (r) => !rows.some((row) => row.register.id === r.id),
  );

  function openCreate() {
    setCreateRegId(availableRegisters[0]?.id ?? 0);
    setCreateModel('');
    setCreateSerial('');
    setCreateConnType('');
    setCreateConnAddr('');
    setCreateError('');
    setShowCreate(true);
  }

  async function handleCreate() {
    if (!createRegId) {
      setCreateError('Select a register.');
      return;
    }
    setCreateBusy(true);
    setCreateError('');
    try {
      await api.put(`/api/registers/${createRegId}/cash-drawer`, {
        model: createModel.trim() || null,
        serial_number: createSerial.trim() || null,
        connection_type: createConnType || null,
        connection_address: createConnAddr.trim() || null,
      });
      setShowCreate(false);
      load();
    } catch (err: any) {
      setCreateError(err?.detail ?? err?.message ?? 'Failed to add cash drawer.');
    } finally {
      setCreateBusy(false);
    }
  }

  function openEdit(row: DrawerRow) {
    setEditRow(row);
    setEditModel(row.drawer.model ?? '');
    setEditSerial(row.drawer.serial_number ?? '');
    setEditConnType(row.drawer.connection_type ?? '');
    setEditConnAddr(row.drawer.connection_address ?? '');
    setEditError('');
  }

  async function handleSave() {
    if (!editRow) return;
    setEditBusy(true);
    setEditError('');
    try {
      await api.put(`/api/registers/${editRow.register.id}/cash-drawer`, {
        model: editModel.trim() || null,
        serial_number: editSerial.trim() || null,
        connection_type: editConnType || null,
        connection_address: editConnAddr.trim() || null,
      });
      setEditRow(null);
      load();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Failed to save.');
    } finally {
      setEditBusy(false);
    }
  }

  async function handleRemove(row: DrawerRow) {
    try {
      await api.delete(`/api/registers/${row.register.id}/cash-drawer`);
      load();
    } catch {
      // silent
    }
  }

  function DrawerFormFields({
    model, setModel, serial, setSerial,
    connType, setConnType, connAddr, setConnAddr,
    registerId, setRegisterId, showRegister,
  }: {
    model: string; setModel: (v: string) => void;
    serial: string; setSerial: (v: string) => void;
    connType: string; setConnType: (v: string) => void;
    connAddr: string; setConnAddr: (v: string) => void;
    registerId?: number; setRegisterId?: (v: number) => void;
    showRegister?: boolean;
  }) {
    return (
      <div className="flex flex-col gap-4">
        {showRegister && setRegisterId && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Register</label>
            <select
              value={String(registerId)}
              onChange={(e) => setRegisterId(Number(e.target.value))}
              className="h-11 rounded-xl border border-border bg-white px-3 text-sm"
            >
              {availableRegisters.map((r) => (
                <option key={r.id} value={r.id}>{r.register_number} — {r.name}</option>
              ))}
            </select>
          </div>
        )}
        <Input label="Model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. APG VB320-BL1616" />
        <Input label="Serial Number" value={serial} onChange={(e) => setSerial(e.target.value)} placeholder="Optional" />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">Connection Type</label>
          <select
            value={connType}
            onChange={(e) => setConnType(e.target.value)}
            className="h-11 rounded-xl border border-border bg-white px-3 text-sm"
          >
            <option value="">None</option>
            {DRAWER_CONN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <Input label="Connection Address" value={connAddr} onChange={(e) => setConnAddr(e.target.value)} placeholder="e.g. COM3, 192.168.1.100" />
      </div>
    );
  }

  const columns = [
    {
      key: 'register',
      header: 'Register',
      render: (row: DrawerRow) => (
        <span className="font-medium">{row.register.register_number} — {row.register.name}</span>
      ),
    },
    {
      key: 'model',
      header: 'Model',
      render: (row: DrawerRow) => (
        <span className="text-slate-600">{row.drawer.model ?? '-'}</span>
      ),
    },
    {
      key: 'connection',
      header: 'Connection',
      render: (row: DrawerRow) => (
        row.drawer.connection_type
          ? <span className="text-slate-600">{row.drawer.connection_type}{row.drawer.connection_address ? ` — ${row.drawer.connection_address}` : ''}</span>
          : <span className="text-slate-400">-</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: DrawerRow) => (
        <Badge variant={row.drawer.is_active ? 'success' : 'muted'}>{row.drawer.is_active ? 'Active' : 'Inactive'}</Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row: DrawerRow) => (
        <div className="flex justify-end gap-1">
          {canManageRegisters ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>Edit</Button>
              <Button variant="danger" size="sm" onClick={() => handleRemove(row)}>Remove</Button>
            </>
          ) : (
            <span className="text-xs text-slate-400">View only</span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {canManageRegisters && (
        <div className="flex justify-end">
          <Button onClick={openCreate} disabled={availableRegisters.length === 0}>Add Cash Drawer</Button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted">Loading cash drawers...</p>
      ) : (
        <DataTable columns={columns} data={rows} emptyMessage="No cash drawers configured. Add a cash drawer to a register to get started." />
      )}

      {/* Create Cash Drawer Dialog */}
      <Dialog open={showCreate && canManageRegisters} onClose={() => setShowCreate(false)} title="Add Cash Drawer">
        {createError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{createError}</div>
        )}
        <DrawerFormFields
          model={createModel} setModel={setCreateModel}
          serial={createSerial} setSerial={setCreateSerial}
          connType={createConnType} setConnType={setCreateConnType}
          connAddr={createConnAddr} setConnAddr={setCreateConnAddr}
          registerId={createRegId} setRegisterId={setCreateRegId}
          showRegister
        />
        <div className="flex gap-2 mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>{createBusy ? 'Adding...' : 'Add'}</Button>
          <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
        </div>
      </Dialog>

      {/* Edit Cash Drawer Dialog */}
      <Dialog open={!!editRow && canManageRegisters} onClose={() => setEditRow(null)} title={`Cash Drawer — ${editRow?.register.name ?? ''}`}>
        {editError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{editError}</div>
        )}
        <DrawerFormFields
          model={editModel} setModel={setEditModel}
          serial={editSerial} setSerial={setEditSerial}
          connType={editConnType} setConnType={setEditConnType}
          connAddr={editConnAddr} setConnAddr={setEditConnAddr}
        />
        <div className="flex gap-2 mt-4">
          <Button onClick={handleSave} disabled={editBusy}>{editBusy ? 'Saving...' : 'Save'}</Button>
          <Button variant="secondary" onClick={() => setEditRow(null)}>Cancel</Button>
        </div>
      </Dialog>
    </div>
  );
}

/* ================================================================== */
/*  PRINTERS TAB                                                       */
/* ================================================================== */

type PrinterData = {
  id: number;
  register_id: number;
  name: string;
  printer_type: string;
  model: string | null;
  serial_number: string | null;
  connection_type: string | null;
  connection_address: string | null;
  paper_width_mm: number | null;
  supports_cut: boolean;
  supports_cash_drawer: boolean;
  is_active: boolean;
};

type PrinterRow = PrinterData & { register_name: string; register_number: string | number };

const PRINTER_TYPES = ['RECEIPT', 'KITCHEN', 'LABEL', 'REPORT'] as const;
const PRINTER_CONN_TYPES = ['USB', 'SERIAL', 'NETWORK', 'BLUETOOTH'] as const;

function PrintersTab() {
  const { hasPermission } = useAuth();
  const canManageRegisters = hasPermission('MANAGE_REGISTER');
  const { currentStoreId: storeId } = useStore();
  const [printers, setPrinters] = useState<PrinterRow[]>([]);
  const [registers, setRegisters] = useState<Register[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createRegId, setCreateRegId] = useState<number>(0);
  const [createName, setCreateName] = useState('');
  const [createType, setCreateType] = useState<string>('RECEIPT');
  const [createModel, setCreateModel] = useState('');
  const [createSerial, setCreateSerial] = useState('');
  const [createConnType, setCreateConnType] = useState('');
  const [createConnAddr, setCreateConnAddr] = useState('');
  const [createPaperWidth, setCreatePaperWidth] = useState('80');
  const [createSupportsCut, setCreateSupportsCut] = useState(true);
  const [createSupportsDrawer, setCreateSupportsDrawer] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');

  // Edit dialog
  const [editPrinter, setEditPrinter] = useState<PrinterRow | null>(null);
  const [editName, setEditName] = useState('');
  const [editType, setEditType] = useState('');
  const [editModel, setEditModel] = useState('');
  const [editSerial, setEditSerial] = useState('');
  const [editConnType, setEditConnType] = useState('');
  const [editConnAddr, setEditConnAddr] = useState('');
  const [editPaperWidth, setEditPaperWidth] = useState('');
  const [editSupportsCut, setEditSupportsCut] = useState(true);
  const [editSupportsDrawer, setEditSupportsDrawer] = useState(false);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ registers: Register[] }>(`/api/registers/?store_id=${storeId}`);
      const regs = res.registers ?? [];
      setRegisters(regs);

      const results = await Promise.allSettled(
        regs.map(async (r) => {
          const p = await api.get<{ printers: PrinterData[] }>(`/api/registers/${r.id}/printers`);
          return (p.printers ?? []).map((pr) => ({
            ...pr,
            register_name: r.name,
            register_number: r.register_number,
          }));
        }),
      );

      const all: PrinterRow[] = [];
      for (const r of results) {
        if (r.status === 'fulfilled') all.push(...r.value);
      }
      setPrinters(all);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load printers.');
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setCreateRegId(registers[0]?.id ?? 0);
    setCreateName('');
    setCreateType('RECEIPT');
    setCreateModel('');
    setCreateSerial('');
    setCreateConnType('');
    setCreateConnAddr('');
    setCreatePaperWidth('80');
    setCreateSupportsCut(true);
    setCreateSupportsDrawer(false);
    setCreateError('');
    setShowCreate(true);
  }

  async function handleCreate() {
    if (!createName.trim() || !createRegId) {
      setCreateError('Register and name are required.');
      return;
    }
    setCreateBusy(true);
    setCreateError('');
    try {
      await api.post(`/api/registers/${createRegId}/printers`, {
        name: createName.trim(),
        printer_type: createType,
        model: createModel.trim() || null,
        serial_number: createSerial.trim() || null,
        connection_type: createConnType || null,
        connection_address: createConnAddr.trim() || null,
        paper_width_mm: createPaperWidth ? Number(createPaperWidth) : null,
        supports_cut: createSupportsCut,
        supports_cash_drawer: createSupportsDrawer,
      });
      setShowCreate(false);
      load();
    } catch (err: any) {
      setCreateError(err?.detail ?? err?.message ?? 'Failed to create printer.');
    } finally {
      setCreateBusy(false);
    }
  }

  function openEdit(p: PrinterRow) {
    setEditPrinter(p);
    setEditName(p.name);
    setEditType(p.printer_type);
    setEditModel(p.model ?? '');
    setEditSerial(p.serial_number ?? '');
    setEditConnType(p.connection_type ?? '');
    setEditConnAddr(p.connection_address ?? '');
    setEditPaperWidth(p.paper_width_mm != null ? String(p.paper_width_mm) : '');
    setEditSupportsCut(p.supports_cut);
    setEditSupportsDrawer(p.supports_cash_drawer);
    setEditError('');
  }

  async function handleEdit() {
    if (!editPrinter) return;
    setEditBusy(true);
    setEditError('');
    try {
      await api.patch(`/api/registers/printers/${editPrinter.id}`, {
        name: editName.trim(),
        printer_type: editType,
        model: editModel.trim() || null,
        serial_number: editSerial.trim() || null,
        connection_type: editConnType || null,
        connection_address: editConnAddr.trim() || null,
        paper_width_mm: editPaperWidth ? Number(editPaperWidth) : null,
        supports_cut: editSupportsCut,
        supports_cash_drawer: editSupportsDrawer,
      });
      setEditPrinter(null);
      load();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Update failed.');
    } finally {
      setEditBusy(false);
    }
  }

  async function handleDelete(p: PrinterRow) {
    try {
      await api.delete(`/api/registers/printers/${p.id}`);
      load();
    } catch {
      // silent
    }
  }

  const columns = [
    {
      key: 'register',
      header: 'Register',
      render: (row: PrinterRow) => (
        <span className="font-medium">{row.register_number} — {row.register_name}</span>
      ),
    },
    {
      key: 'name',
      header: 'Printer',
      render: (row: PrinterRow) => <span>{row.name}</span>,
    },
    {
      key: 'type',
      header: 'Type',
      render: (row: PrinterRow) => <Badge variant="primary">{row.printer_type}</Badge>,
    },
    {
      key: 'model',
      header: 'Model',
      render: (row: PrinterRow) => <span className="text-slate-600">{row.model ?? '-'}</span>,
    },
    {
      key: 'connection',
      header: 'Connection',
      render: (row: PrinterRow) => (
        row.connection_type
          ? <span className="text-slate-600">{row.connection_type}{row.connection_address ? ` — ${row.connection_address}` : ''}</span>
          : <span className="text-slate-400">-</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: PrinterRow) => (
        <Badge variant={row.is_active ? 'success' : 'muted'}>{row.is_active ? 'Active' : 'Inactive'}</Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row: PrinterRow) => (
        <div className="flex justify-end gap-1">
          {canManageRegisters ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>Edit</Button>
              <Button variant="danger" size="sm" onClick={() => handleDelete(row)}>Remove</Button>
            </>
          ) : (
            <span className="text-xs text-slate-400">View only</span>
          )}
        </div>
      ),
    },
  ];

  function PrinterFormFields({
    name, setName, type, setType, model, setModel, serial, setSerial,
    connType, setConnType, connAddr, setConnAddr, paperWidth, setPaperWidth,
    supportsCut, setSupportsCut, supportsDrawer, setSupportsDrawer,
    registerId, setRegisterId, showRegister,
  }: {
    name: string; setName: (v: string) => void;
    type: string; setType: (v: string) => void;
    model: string; setModel: (v: string) => void;
    serial: string; setSerial: (v: string) => void;
    connType: string; setConnType: (v: string) => void;
    connAddr: string; setConnAddr: (v: string) => void;
    paperWidth: string; setPaperWidth: (v: string) => void;
    supportsCut: boolean; setSupportsCut: (v: boolean) => void;
    supportsDrawer: boolean; setSupportsDrawer: (v: boolean) => void;
    registerId?: number; setRegisterId?: (v: number) => void;
    showRegister?: boolean;
  }) {
    return (
      <div className="flex flex-col gap-4">
        {showRegister && setRegisterId && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Register</label>
            <select
              value={String(registerId)}
              onChange={(e) => setRegisterId(Number(e.target.value))}
              className="h-11 rounded-xl border border-border bg-white px-3 text-sm"
            >
              {registers.map((r) => (
                <option key={r.id} value={r.id}>{r.register_number} — {r.name}</option>
              ))}
            </select>
          </div>
        )}
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Front Receipt Printer" />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)} className="h-11 rounded-xl border border-border bg-white px-3 text-sm">
            {PRINTER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <Input label="Model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. Epson TM-T88VI" />
        <Input label="Serial Number" value={serial} onChange={(e) => setSerial(e.target.value)} placeholder="Optional" />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">Connection Type</label>
          <select value={connType} onChange={(e) => setConnType(e.target.value)} className="h-11 rounded-xl border border-border bg-white px-3 text-sm">
            <option value="">None</option>
            {PRINTER_CONN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <Input label="Connection Address" value={connAddr} onChange={(e) => setConnAddr(e.target.value)} placeholder="e.g. 192.168.1.100:9100" />
        <Input label="Paper Width (mm)" value={paperWidth} onChange={(e) => setPaperWidth(e.target.value)} placeholder="e.g. 80" />
        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={supportsCut} onChange={(e) => setSupportsCut(e.target.checked)} className="rounded" />
            Supports auto-cut
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={supportsDrawer} onChange={(e) => setSupportsDrawer(e.target.checked)} className="rounded" />
            Can kick cash drawer
          </label>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {canManageRegisters && (
        <div className="flex justify-end">
          <Button onClick={openCreate} disabled={registers.length === 0}>Add Printer</Button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted">Loading printers...</p>
      ) : (
        <DataTable columns={columns} data={printers} emptyMessage="No printers configured. Add a printer to a register to get started." />
      )}

      {/* Create Printer Dialog */}
      <Dialog open={showCreate && canManageRegisters} onClose={() => setShowCreate(false)} title="Add Printer">
        {createError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{createError}</div>
        )}
        <PrinterFormFields
          name={createName} setName={setCreateName}
          type={createType} setType={setCreateType}
          model={createModel} setModel={setCreateModel}
          serial={createSerial} setSerial={setCreateSerial}
          connType={createConnType} setConnType={setCreateConnType}
          connAddr={createConnAddr} setConnAddr={setCreateConnAddr}
          paperWidth={createPaperWidth} setPaperWidth={setCreatePaperWidth}
          supportsCut={createSupportsCut} setSupportsCut={setCreateSupportsCut}
          supportsDrawer={createSupportsDrawer} setSupportsDrawer={setCreateSupportsDrawer}
          registerId={createRegId} setRegisterId={setCreateRegId}
          showRegister
        />
        <div className="flex gap-2 mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>{createBusy ? 'Creating...' : 'Create'}</Button>
          <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
        </div>
      </Dialog>

      {/* Edit Printer Dialog */}
      <Dialog open={!!editPrinter && canManageRegisters} onClose={() => setEditPrinter(null)} title={`Edit — ${editPrinter?.name ?? ''}`}>
        {editError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{editError}</div>
        )}
        <PrinterFormFields
          name={editName} setName={setEditName}
          type={editType} setType={setEditType}
          model={editModel} setModel={setEditModel}
          serial={editSerial} setSerial={setEditSerial}
          connType={editConnType} setConnType={setEditConnType}
          connAddr={editConnAddr} setConnAddr={setEditConnAddr}
          paperWidth={editPaperWidth} setPaperWidth={setEditPaperWidth}
          supportsCut={editSupportsCut} setSupportsCut={setEditSupportsCut}
          supportsDrawer={editSupportsDrawer} setSupportsDrawer={setEditSupportsDrawer}
        />
        <div className="flex gap-2 mt-4">
          <Button onClick={handleEdit} disabled={editBusy}>{editBusy ? 'Saving...' : 'Save'}</Button>
          <Button variant="secondary" onClick={() => setEditPrinter(null)}>Cancel</Button>
        </div>
      </Dialog>
    </div>
  );
}
