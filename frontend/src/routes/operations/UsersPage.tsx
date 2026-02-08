import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input, Select } from '@/components/ui/Input';

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

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function UsersPage() {
  const { currentStoreId: storeId } = useStore();

  // Users list
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<{ users: User[] }>(
        `/api/admin/users?include_inactive=${showInactive}`,
      );
      setUsers(res.users ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  const loadRoles = useCallback(async () => {
    try {
      const res = await api.get<{ roles: Role[] }>('/api/admin/roles');
      setRoles(res.roles ?? []);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadUsers();
    loadRoles();
  }, [loadUsers, loadRoles]);

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

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Users</h1>
        <p className="text-sm text-muted mt-1">
          Manage user accounts, roles, and permissions.
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
        <div className="p-5 pb-0 flex items-center justify-between">
          <CardTitle>Users</CardTitle>
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
                    <th className="py-2 px-3 font-medium">Status</th>
                    <th className="py-2 px-5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-border/50 hover:bg-slate-50">
                      <td className="py-2.5 px-5 font-medium">{u.username}</td>
                      <td className="py-2.5 px-3 text-muted">{u.email}</td>
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
                <p className="text-xs text-muted font-medium uppercase tracking-wider">Store ID</p>
                <p className="text-sm mt-1">{selectedUser.store_id ?? '-'}</p>
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

            {/* Permissions */}
            {selectedUser.permissions && selectedUser.permissions.length > 0 && (
              <div>
                <p className="text-xs text-muted font-medium uppercase tracking-wider mb-2">Permissions</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedUser.permissions.map((perm) => (
                    <Badge key={perm} variant="muted">{perm}</Badge>
                  ))}
                </div>
              </div>
            )}

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
