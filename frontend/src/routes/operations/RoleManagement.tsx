import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { DataTable } from '@/components/ui/DataTable';
import { Tabs } from '@/components/ui/Tabs';
import {
  type Permission,
  WORKSPACE_GROUPS,
  CATEGORY_LABELS,
  groupPermissions,
} from '@/lib/permission-groups';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type RoleSummary = {
  id: number;
  name: string;
  description: string | null;
  permission_count: number;
};

type RoleDetail = {
  id: number;
  name: string;
  description: string | null;
  permissions: Permission[];
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RoleManagement() {
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [createBusy, setCreateBusy] = useState(false);

  // Detail dialog
  const [detail, setDetail] = useState<RoleDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [permsCatalog, setPermsCatalog] = useState<Permission[]>([]);
  const [permWorkspace, setPermWorkspace] = useState('sales');
  const [toggleBusy, setToggleBusy] = useState<string | null>(null);

  const loadRoles = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ roles: RoleSummary[] }>('/api/admin/roles');
      setRoles(res.roles ?? []);
    } catch (err: unknown) {
      const e = err as Record<string, string>;
      setError(e?.detail ?? e?.message ?? 'Failed to load roles.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPermsCatalog = useCallback(async () => {
    try {
      const res = await api.get<{ permissions: Permission[] }>('/api/admin/permissions');
      setPermsCatalog(res.permissions ?? []);
    } catch {
      setPermsCatalog([]);
    }
  }, []);

  useEffect(() => {
    loadRoles();
    loadPermsCatalog();
  }, [loadRoles, loadPermsCatalog]);

  async function openDetail(roleName: string) {
    setDetailLoading(true);
    setError('');
    try {
      const res = await api.get<{ role: RoleDetail }>(
        `/api/admin/roles/${encodeURIComponent(roleName)}`,
      );
      setDetail(res.role);
      setPermWorkspace('sales');
    } catch (err: unknown) {
      const e = err as Record<string, string>;
      setError(e?.detail ?? e?.message ?? 'Failed to load role details.');
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleCreate() {
    if (!newName.trim()) {
      setError('Role name is required.');
      return;
    }
    setCreateBusy(true);
    setError('');
    try {
      await api.post('/api/admin/roles', {
        name: newName.trim(),
        description: newDesc.trim() || null,
      });
      setShowCreate(false);
      setNewName('');
      setNewDesc('');
      loadRoles();
    } catch (err: unknown) {
      const e = err as Record<string, string>;
      setError(e?.detail ?? e?.message ?? 'Failed to create role.');
    } finally {
      setCreateBusy(false);
    }
  }

  async function togglePermission(permCode: string, hasIt: boolean) {
    if (!detail) return;
    setToggleBusy(permCode);
    try {
      if (hasIt) {
        await api.delete(
          `/api/admin/roles/${encodeURIComponent(detail.name)}/permissions/${encodeURIComponent(permCode)}`,
        );
      } else {
        await api.post(
          `/api/admin/roles/${encodeURIComponent(detail.name)}/permissions`,
          { permission_code: permCode },
        );
      }
      // Refresh detail
      await openDetail(detail.name);
      loadRoles(); // Update permission counts
    } catch (err: unknown) {
      const e = err as Record<string, string>;
      setError(e?.detail ?? e?.message ?? 'Failed to update permission.');
    } finally {
      setToggleBusy(null);
    }
  }

  const rolePermCodes = new Set(detail?.permissions?.map((p) => p.code) ?? []);
  const catalogByWorkspace = groupPermissions(permsCatalog);

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (r: RoleSummary) => <span className="font-medium">{r.name}</span>,
    },
    {
      key: 'description',
      header: 'Description',
      render: (r: RoleSummary) => (
        <span className="text-muted">{r.description || '-'}</span>
      ),
    },
    {
      key: 'permission_count',
      header: 'Permissions',
      render: (r: RoleSummary) => <Badge variant="muted">{r.permission_count}</Badge>,
    },
    {
      key: 'actions',
      header: '',
      render: (r: RoleSummary) => (
        <Button variant="ghost" size="sm" onClick={() => openDetail(r.name)}>
          View
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between">
          <CardTitle>Roles</CardTitle>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            + Create Role
          </Button>
        </div>
        <div className="mt-4">
          {loading ? (
            <div className="px-5 pb-5 text-sm text-muted">Loading roles...</div>
          ) : (
            <DataTable
              columns={columns}
              data={roles}
              emptyMessage="No roles defined."
            />
          )}
        </div>
      </Card>

      {/* Create Role Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create Role">
        <div className="flex flex-col gap-4">
          <Input
            label="Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. shift-lead"
          />
          <Input
            label="Description"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Optional"
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

      {/* Role Detail Dialog */}
      <Dialog
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail ? `Role: ${detail.name}` : 'Role Details'}
        wide
      >
        {detailLoading ? (
          <p className="text-sm text-muted">Loading...</p>
        ) : detail ? (
          <div className="flex flex-col gap-4">
            {detail.description && (
              <p className="text-sm text-muted">{detail.description}</p>
            )}

            <p className="text-xs text-muted font-medium uppercase tracking-wider">
              Permissions ({detail.permissions.length})
            </p>

            <Tabs
              tabs={Object.values(WORKSPACE_GROUPS).map((g) => g.label)}
              active={WORKSPACE_GROUPS[permWorkspace]?.label ?? 'Sales'}
              onChange={(tab) => {
                const key = Object.entries(WORKSPACE_GROUPS).find(
                  ([, v]) => v.label === tab,
                )?.[0];
                if (key) setPermWorkspace(key);
              }}
            />

            <div className="space-y-4">
              {WORKSPACE_GROUPS[permWorkspace]?.categories.map((cat) => {
                const catPerms = catalogByWorkspace[permWorkspace]?.[cat] ?? [];
                if (catPerms.length === 0) return null;
                return (
                  <div key={cat}>
                    <p className="text-xs font-medium text-slate-500 mb-2">
                      {CATEGORY_LABELS[cat] ?? cat}
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {catPerms.map((p) => {
                        const has = rolePermCodes.has(p.code);
                        const busy = toggleBusy === p.code;
                        return (
                          <label
                            key={p.code}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer
                              transition-colors ${has ? 'bg-primary-light/50' : 'hover:bg-slate-50'}
                              ${busy ? 'opacity-50 pointer-events-none' : ''}`}
                          >
                            <input
                              type="checkbox"
                              checked={has}
                              onChange={() => togglePermission(p.code, has)}
                              disabled={busy}
                              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                            />
                            <div>
                              <span className="font-medium">{p.name ?? p.code}</span>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              {WORKSPACE_GROUPS[permWorkspace]?.categories.every(
                (cat) => (catalogByWorkspace[permWorkspace]?.[cat] ?? []).length === 0,
              ) && <p className="text-sm text-muted">No permissions in this workspace.</p>}
            </div>

            <div className="flex gap-2 pt-2 border-t border-border">
              <Button variant="secondary" size="sm" onClick={() => setDetail(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
