import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input, Select } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type User = {
  id: number;
  username: string;
  email: string;
  store_id: number | null;
  is_active: boolean;
  created_at: string;
  roles?: string[];
  permissions?: string[];
};

type Role = {
  id: number;
  name: string;
  description: string | null;
};
type Permission = { code: string; name?: string; category?: string };
type Override = {
  id: number;
  user_id: number;
  permission_code: string;
  override_type: 'GRANT' | 'DENY';
  is_active: boolean;
};

type ManagerStoreAccess = {
  id: number;
  user_id: number;
  store_id: number;
  granted_by_user_id: number | null;
  granted_at: string;
};

/* ------------------------------------------------------------------ */
/*  Permission workspace grouping                                      */
/* ------------------------------------------------------------------ */

const WORKSPACE_GROUPS: Record<string, { label: string; categories: string[] }> = {
  sales: {
    label: 'Sales',
    categories: ['SALES', 'REGISTERS'],
  },
  inventory: {
    label: 'Inventory',
    categories: ['INVENTORY'],
  },
  documents: {
    label: 'Documents',
    categories: ['DOCUMENTS'],
  },
  communications: {
    label: 'Communications',
    categories: ['COMMUNICATIONS', 'PROMOTIONS'],
  },
  timekeeping: {
    label: 'Timekeeping',
    categories: ['TIMEKEEPING'],
  },
  management: {
    label: 'Management',
    categories: ['USERS', 'ORGANIZATION', 'DEVICES', 'SYSTEM'],
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  SALES: 'Sales',
  REGISTERS: 'Registers',
  INVENTORY: 'Inventory',
  DOCUMENTS: 'Documents',
  COMMUNICATIONS: 'Communications',
  PROMOTIONS: 'Promotions',
  TIMEKEEPING: 'Timekeeping',
  USERS: 'Users',
  ORGANIZATION: 'Organization',
  DEVICES: 'Devices',
  SYSTEM: 'System',
};

function groupPermissions(permissions: Permission[]) {
  const grouped: Record<string, Record<string, Permission[]>> = {};
  for (const ws of Object.keys(WORKSPACE_GROUPS)) {
    grouped[ws] = {};
    for (const cat of WORKSPACE_GROUPS[ws].categories) {
      grouped[ws][cat] = [];
    }
  }
  for (const p of permissions) {
    const cat = p.category ?? 'SYSTEM';
    for (const [ws, config] of Object.entries(WORKSPACE_GROUPS)) {
      if (config.categories.includes(cat)) {
        if (!grouped[ws][cat]) grouped[ws][cat] = [];
        grouped[ws][cat].push(p);
        break;
      }
    }
  }
  return grouped;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function UsersPage() {
  const { currentStoreId: storeId, stores } = useStore();
  const { hasPermission } = useAuth();
  const canScopeAcrossStores = hasPermission('MANAGE_STORES') && stores.length > 1;

  // Users list
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [filterStoreId, setFilterStoreId] = useState<number | null>(null);
  const [orgWide, setOrgWide] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [permissionsCatalog, setPermissionsCatalog] = useState<Permission[]>([]);

  // Create form
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('');
  const [createBusy, setCreateBusy] = useState(false);

  // Detail dialog
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [assignRole, setAssignRole] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [overridePerm, setOverridePerm] = useState('');
  const [overrideType, setOverrideType] = useState<'GRANT' | 'DENY'>('GRANT');
  const [permWorkspace, setPermWorkspace] = useState('sales');
  const [managerStoreAccess, setManagerStoreAccess] = useState<ManagerStoreAccess[]>([]);
  const [effectiveManagerStoreIds, setEffectiveManagerStoreIds] = useState<number[]>([]);
  const [newManagerStoreId, setNewManagerStoreId] = useState<number | null>(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let url = `/api/admin/users?include_inactive=${showInactive}`;
      if (!orgWide && (filterStoreId ?? storeId)) {
        url += `&store_id=${filterStoreId ?? storeId}`;
      }
      const res = await api.get<{ users: User[] }>(url);
      setUsers(res.users ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  }, [showInactive, orgWide, filterStoreId, storeId]);

  const loadRoles = useCallback(async () => {
    try {
      const res = await api.get<{ roles: Role[] }>('/api/admin/roles');
      setRoles(res.roles ?? []);
    } catch {
      // silent
    }
  }, []);

  const loadPermissions = useCallback(async () => {
    try {
      const res = await api.get<{ permissions: Permission[] }>('/api/admin/permissions');
      setPermissionsCatalog(res.permissions ?? []);
    } catch {
      setPermissionsCatalog([]);
    }
  }, []);

  useEffect(() => {
    loadUsers();
    loadRoles();
    loadPermissions();
  }, [loadUsers, loadRoles, loadPermissions]);

  async function handleCreate() {
    if (!newUsername.trim() || !newEmail.trim() || !newPassword.trim()) {
      setError('Username, email, and password are required.');
      return;
    }
    setCreateBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = {
        username: newUsername.trim(),
        email: newEmail.trim(),
        password: newPassword.trim(),
        store_id: storeId,
      };
      if (newRole) body.role = newRole;
      await api.post('/api/admin/users', body);
      setNewUsername('');
      setNewEmail('');
      setNewPassword('');
      setNewRole('');
      setSuccess('User created successfully.');
      loadUsers();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to create user.');
    } finally {
      setCreateBusy(false);
    }
  }

  async function openDetails(userId: number) {
    setDetailLoading(true);
    setError('');
    try {
      const res = await api.get<{ user: User }>(`/api/admin/users/${userId}`);
      setSelectedUser(res.user);
      setAssignRole('');
      const o = await api.get<{ overrides: Override[] }>(`/api/admin/users/${userId}/permission-overrides`);
      setOverrides(o.overrides ?? []);
      const ms = await api.get<{
        items: ManagerStoreAccess[];
        effective_store_ids: number[];
        primary_store_id: number | null;
      }>(`/api/admin/users/${userId}/manager-stores`);
      setManagerStoreAccess(ms.items ?? []);
      setEffectiveManagerStoreIds(ms.effective_store_ids ?? []);
      setNewManagerStoreId(null);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load user details.');
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleDeactivate(userId: number) {
    setActionBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/admin/users/${userId}/deactivate`);
      setSuccess('User deactivated.');
      loadUsers();
      if (selectedUser?.id === userId) {
        openDetails(userId);
      }
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to deactivate user.');
    } finally {
      setActionBusy(false);
    }
  }

  async function handleReactivate(userId: number) {
    setActionBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/admin/users/${userId}/reactivate`);
      setSuccess('User reactivated.');
      loadUsers();
      if (selectedUser?.id === userId) {
        openDetails(userId);
      }
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to reactivate user.');
    } finally {
      setActionBusy(false);
    }
  }

  async function handleAssignRole() {
    if (!selectedUser || !assignRole) return;
    setActionBusy(true);
    setError('');
    try {
      await api.post(`/api/admin/users/${selectedUser.id}/roles`, {
        role_name: assignRole,
      });
      setAssignRole('');
      openDetails(selectedUser.id);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to assign role.');
    } finally {
      setActionBusy(false);
    }
  }

  async function handleRemoveRole(roleName: string) {
    if (!selectedUser) return;
    setActionBusy(true);
    setError('');
    try {
      await api.delete(
        `/api/admin/users/${selectedUser.id}/roles/${encodeURIComponent(roleName)}`,
      );
      openDetails(selectedUser.id);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to remove role.');
    } finally {
      setActionBusy(false);
    }
  }

  async function addOverride() {
    if (!selectedUser || !overridePerm) return;
    setActionBusy(true);
    setError('');
    try {
      await api.post(`/api/admin/users/${selectedUser.id}/permission-overrides`, {
        permission_code: overridePerm,
        override_type: overrideType,
      });
      setOverridePerm('');
      openDetails(selectedUser.id);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to save permission override.');
    } finally {
      setActionBusy(false);
    }
  }

  async function revokeOverride(code: string) {
    if (!selectedUser) return;
    setActionBusy(true);
    setError('');
    try {
      await api.delete(`/api/admin/users/${selectedUser.id}/permission-overrides/${encodeURIComponent(code)}`);
      openDetails(selectedUser.id);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to revoke permission override.');
    } finally {
      setActionBusy(false);
    }
  }

  async function addManagerStoreAccess() {
    if (!selectedUser || !newManagerStoreId) return;
    setActionBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/admin/users/${selectedUser.id}/manager-stores`, {
        store_id: newManagerStoreId,
      });
      await openDetails(selectedUser.id);
      setSuccess('Manager store access granted.');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to grant manager store access.');
    } finally {
      setActionBusy(false);
    }
  }

  async function removeManagerStoreAccess(storeIdToRemove: number) {
    if (!selectedUser) return;
    setActionBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.delete(`/api/admin/users/${selectedUser.id}/manager-stores/${storeIdToRemove}`);
      await openDetails(selectedUser.id);
      setSuccess('Manager store access removed.');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to remove manager store access.');
    } finally {
      setActionBusy(false);
    }
  }

  // Group user permissions by workspace for display
  const userPermsByWorkspace = selectedUser?.permissions
    ? groupPermissions(
        selectedUser.permissions.map((code) => {
          const cat = permissionsCatalog.find((p) => p.code === code);
          return { code, name: cat?.name, category: cat?.category };
        }),
      )
    : null;

  // Group catalog permissions by workspace for override picker
  const catalogByWorkspace = groupPermissions(permissionsCatalog);

  // Store name lookup
  const storeNameMap: Record<number, string> = {};
  for (const s of stores) {
    storeNameMap[s.id] = s.name;
  }
  const explicitManagerStoreIds = new Set(managerStoreAccess.map((a) => a.store_id));
  const addableManagerStores = stores.filter(
    (s) => !effectiveManagerStoreIds.includes(s.id),
  );

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Users</h1>
        <p className="text-sm text-muted mt-1">
          Manage accounts, roles, and direct permission overrides in one place.
        </p>
      </div>

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

      {/* Create User */}
      <Card>
        <CardTitle>Create User</CardTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          <Input
            label="Username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            placeholder="johndoe"
          />
          <Input
            label="Email"
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="john@example.com"
          />
          <Input
            label="Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Min 8 characters"
          />
          <Select
            label="Role"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            options={[
              { value: '', label: '-- Select Role --' },
              ...roles.map((r) => ({ value: r.name, label: r.name })),
            ]}
          />
        </div>
        <div className="mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>
            Create User
          </Button>
        </div>
      </Card>

      {/* Users Table */}
      <Card padding={false}>
        <div className="p-5 pb-0 flex items-center justify-between flex-wrap gap-3">
          <CardTitle>Users</CardTitle>
          <div className="flex items-center gap-4 flex-wrap">
            {/* Admin store filter */}
            {canScopeAcrossStores && (
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={orgWide}
                    onChange={(e) => {
                      setOrgWide(e.target.checked);
                      if (e.target.checked) setFilterStoreId(null);
                    }}
                    className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                  />
                  <span className="text-sm text-slate-600">All stores</span>
                </label>
                {!orgWide && (
                  <select
                    className="rounded-lg border border-border px-2 py-1 text-sm"
                    value={filterStoreId ?? storeId ?? ''}
                    onChange={(e) => setFilterStoreId(Number(e.target.value))}
                  >
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                )}
              </div>
            )}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
              />
              <span className="text-sm text-slate-600">Show inactive</span>
            </label>
          </div>
        </div>

        <div className="mt-4">
          {loading ? (
            <div className="px-5 pb-5 text-sm text-muted">Loading users...</div>
          ) : users.length === 0 ? (
            <div className="px-5 pb-5 text-sm text-muted">No users found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="py-2 px-5 font-medium">Username</th>
                    <th className="py-2 px-3 font-medium">Email</th>
                    {orgWide && <th className="py-2 px-3 font-medium">Store</th>}
                    <th className="py-2 px-3 font-medium">Roles</th>
                    <th className="py-2 px-3 font-medium">Status</th>
                    <th className="py-2 px-5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-border/50 hover:bg-slate-50">
                      <td className="py-2.5 px-5 font-medium">{u.username}</td>
                      <td className="py-2.5 px-3 text-muted">{u.email}</td>
                      {orgWide && (
                        <td className="py-2.5 px-3 text-muted">
                          {u.store_id ? (storeNameMap[u.store_id] ?? `#${u.store_id}`) : '-'}
                        </td>
                      )}
                      <td className="py-2.5 px-3">
                        <div className="flex gap-1 flex-wrap">
                          {u.roles?.map((r) => (
                            <Badge key={r} variant="primary">{r}</Badge>
                          ))}
                          {(!u.roles || u.roles.length === 0) && (
                            <span className="text-muted text-xs">None</span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={u.is_active ? 'success' : 'muted'}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-5 text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDetails(u.id)}
                          >
                            Details
                          </Button>
                          {u.is_active ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeactivate(u.id)}
                              disabled={actionBusy}
                            >
                              Deactivate
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleReactivate(u.id)}
                              disabled={actionBusy}
                            >
                              Reactivate
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {/* User Details Dialog */}
      <Dialog
        open={!!selectedUser}
        onClose={() => setSelectedUser(null)}
        title="User Details"
        wide
      >
        {detailLoading ? (
          <p className="text-sm text-muted">Loading...</p>
        ) : selectedUser ? (
          <div className="flex flex-col gap-5">
            {/* Basic Info */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Username</p>
                <p className="text-sm font-semibold mt-1">{selectedUser.username}</p>
              </div>
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Email</p>
                <p className="text-sm mt-1">{selectedUser.email}</p>
              </div>
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Store</p>
                <p className="text-sm mt-1">
                  {selectedUser.store_id
                    ? (storeNameMap[selectedUser.store_id] ?? `#${selectedUser.store_id}`)
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Status</p>
                <div className="mt-1">
                  <Badge variant={selectedUser.is_active ? 'success' : 'muted'}>
                    {selectedUser.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Created</p>
                <p className="text-sm mt-1">{formatDateTime(selectedUser.created_at)}</p>
              </div>
            </div>

            {/* Managerial Store Access */}
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider mb-2">Managerial Store Access</p>
              <div className="flex flex-wrap gap-2">
                {effectiveManagerStoreIds.length === 0 ? (
                  <p className="text-sm text-muted">No managerial store access assigned.</p>
                ) : (
                  effectiveManagerStoreIds.map((sid) => {
                    const isPrimary = selectedUser.store_id === sid;
                    const isExplicit = explicitManagerStoreIds.has(sid);
                    return (
                      <div key={sid} className="flex items-center gap-1">
                        <Badge variant={isPrimary ? 'primary' : 'muted'}>
                          {storeNameMap[sid] ?? `#${sid}`}{isPrimary ? ' (Primary)' : ''}
                        </Badge>
                        {!isPrimary && isExplicit && (
                          <button
                            onClick={() => removeManagerStoreAccess(sid)}
                            disabled={actionBusy}
                            className="text-red-400 hover:text-red-600 text-xs font-bold px-1 cursor-pointer"
                            title="Revoke store access"
                          >
                            x
                          </button>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
              <div className="flex gap-2 mt-3">
                <Select
                  label=""
                  value={newManagerStoreId ? String(newManagerStoreId) : ''}
                  onChange={(e) => setNewManagerStoreId(e.target.value ? Number(e.target.value) : null)}
                  options={[
                    { value: '', label: '-- Grant Store Access --' },
                    ...addableManagerStores.map((s) => ({ value: String(s.id), label: s.name })),
                  ]}
                />
                <div className="flex items-end">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={addManagerStoreAccess}
                    disabled={!newManagerStoreId || actionBusy}
                  >
                    Grant
                  </Button>
                </div>
              </div>
            </div>

            {/* Roles */}
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider mb-2">Roles</p>
              {selectedUser.roles && selectedUser.roles.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {selectedUser.roles.map((role) => (
                    <div key={role} className="flex items-center gap-1">
                      <Badge variant="primary">{role}</Badge>
                      <button
                        onClick={() => handleRemoveRole(role)}
                        disabled={actionBusy}
                        className="text-red-400 hover:text-red-600 text-xs font-bold px-1 cursor-pointer"
                        title="Remove role"
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">No roles assigned.</p>
              )}

              <div className="flex gap-2 mt-3">
                <Select
                  label=""
                  value={assignRole}
                  onChange={(e) => setAssignRole(e.target.value)}
                  options={[
                    { value: '', label: '-- Assign Role --' },
                    ...roles
                      .filter((r) => !selectedUser.roles?.includes(r.name))
                      .map((r) => ({ value: r.name, label: r.name })),
                  ]}
                />
                <div className="flex items-end">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAssignRole}
                    disabled={!assignRole || actionBusy}
                  >
                    Assign
                  </Button>
                </div>
              </div>
            </div>

            {/* Permissions — Workspace-scoped tabs */}
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider mb-2">Permissions</p>
              <Tabs
                tabs={Object.values(WORKSPACE_GROUPS).map((g) => g.label)}
                active={WORKSPACE_GROUPS[permWorkspace]?.label ?? 'Sales'}
                onChange={(tab) => {
                  const key = Object.entries(WORKSPACE_GROUPS).find(([, v]) => v.label === tab)?.[0];
                  if (key) setPermWorkspace(key);
                }}
              />
              {userPermsByWorkspace && (
                <div className="mt-3 space-y-3">
                  {WORKSPACE_GROUPS[permWorkspace]?.categories.map((cat) => {
                    const perms = userPermsByWorkspace[permWorkspace]?.[cat] ?? [];
                    if (perms.length === 0) return null;
                    return (
                      <div key={cat}>
                        <p className="text-xs font-medium text-slate-500 mb-1">{CATEGORY_LABELS[cat] ?? cat}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {perms.map((p) => (
                            <Badge key={p.code} variant="muted">{p.name ?? p.code}</Badge>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                  {WORKSPACE_GROUPS[permWorkspace]?.categories.every(
                    (cat) => (userPermsByWorkspace[permWorkspace]?.[cat] ?? []).length === 0,
                  ) && (
                    <p className="text-sm text-muted">No permissions in this workspace.</p>
                  )}
                </div>
              )}
              {!userPermsByWorkspace && (
                <p className="text-sm text-muted mt-2">No permissions data.</p>
              )}
            </div>

            {/* Permission Overrides */}
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider mb-2">Permission Overrides</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Select
                  label=""
                  value={overridePerm}
                  onChange={(e) => setOverridePerm(e.target.value)}
                  options={[
                    { value: '', label: '-- Permission --' },
                    ...Object.entries(catalogByWorkspace).flatMap(([ws, cats]) =>
                      Object.entries(cats).flatMap(([, perms]) =>
                        perms.map((p) => ({
                          value: p.code,
                          label: `${WORKSPACE_GROUPS[ws].label} / ${p.name ?? p.code}`,
                        })),
                      ),
                    ),
                  ]}
                />
                <Select
                  label=""
                  value={overrideType}
                  onChange={(e) => setOverrideType(e.target.value as 'GRANT' | 'DENY')}
                  options={[
                    { value: 'GRANT', label: 'GRANT' },
                    { value: 'DENY', label: 'DENY' },
                  ]}
                />
                <div className="flex items-end">
                  <Button variant="secondary" size="sm" onClick={addOverride} disabled={!overridePerm || actionBusy}>
                    Add Override
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {overrides.length === 0 ? (
                  <p className="text-sm text-muted">No direct overrides.</p>
                ) : (
                  overrides.map((o) => (
                    <div key={o.id} className="flex items-center gap-1">
                      <Badge variant={o.override_type === 'GRANT' ? 'success' : 'danger'}>
                        {o.override_type}: {o.permission_code}
                      </Badge>
                      <button
                        onClick={() => revokeOverride(o.permission_code)}
                        disabled={actionBusy}
                        className="text-red-400 hover:text-red-600 text-xs font-bold px-1 cursor-pointer"
                      >
                        x
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-border">
              {selectedUser.is_active ? (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleDeactivate(selectedUser.id)}
                  disabled={actionBusy}
                >
                  Deactivate User
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => handleReactivate(selectedUser.id)}
                  disabled={actionBusy}
                >
                  Reactivate User
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedUser(null)}
              >
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
