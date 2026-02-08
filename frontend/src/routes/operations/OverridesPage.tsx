import { useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Input, Select } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type Override = {
  id: number;
  user_id: number;
  permission_code: string;
  override_type: string;
  is_active: boolean;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function OverridesPage() {
  const [userId, setUserId] = useState('');
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // New override form
  const [permissionCode, setPermissionCode] = useState('');
  const [overrideType, setOverrideType] = useState('GRANT');
  const [saveBusy, setSaveBusy] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState<string | null>(null);

  async function loadOverrides() {
    if (!userId.trim()) {
      setError('Enter a User ID.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.get<{ overrides: Override[] }>(
        `/api/admin/users/${userId.trim()}/permission-overrides`,
      );
      setOverrides(res.overrides ?? []);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load overrides.');
      setOverrides([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!userId.trim()) {
      setError('Enter a User ID first.');
      return;
    }
    if (!permissionCode.trim()) {
      setError('Enter a permission code.');
      return;
    }
    setSaveBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/admin/users/${userId.trim()}/permission-overrides`, {
        permission_code: permissionCode.trim(),
        override_type: overrideType,
      });
      setPermissionCode('');
      setSuccess('Override saved.');
      loadOverrides();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to save override.');
    } finally {
      setSaveBusy(false);
    }
  }

  async function handleRevoke(code: string) {
    if (!userId.trim()) return;
    setRevokeBusy(code);
    setError('');
    setSuccess('');
    try {
      await api.delete(
        `/api/admin/users/${userId.trim()}/permission-overrides/${encodeURIComponent(code)}`,
      );
      setSuccess(`Override for "${code}" revoked.`);
      loadOverrides();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to revoke override.');
    } finally {
      setRevokeBusy(null);
    }
  }

  const columns = [
    {
      key: 'permission_code',
      header: 'Permission',
      render: (o: Override) => (
        <span className="font-mono text-xs">{o.permission_code}</span>
      ),
    },
    {
      key: 'override_type',
      header: 'Type',
      render: (o: Override) => (
        <Badge variant={o.override_type === 'GRANT' ? 'success' : 'danger'}>
          {o.override_type}
        </Badge>
      ),
    },
    {
      key: 'is_active',
      header: 'Active',
      render: (o: Override) => (
        <Badge variant={o.is_active ? 'success' : 'muted'}>
          {o.is_active ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      className: 'text-right',
      render: (o: Override) => (
        <Button
          variant="danger"
          size="sm"
          onClick={() => handleRevoke(o.permission_code)}
          disabled={revokeBusy === o.permission_code}
        >
          {revokeBusy === o.permission_code ? 'Revoking...' : 'Revoke'}
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Permission Overrides</h1>
        <p className="text-sm text-muted mt-1">
          Grant or deny specific permissions for individual users.
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

      {/* User lookup */}
      <Card>
        <CardTitle>Load User Overrides</CardTitle>
        <div className="flex gap-2 mt-4 items-end">
          <div className="flex-1">
            <Input
              label="User ID"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter user ID"
              onKeyDown={(e) => e.key === 'Enter' && loadOverrides()}
            />
          </div>
          <Button onClick={loadOverrides} disabled={loading}>
            {loading ? 'Loading...' : 'Load'}
          </Button>
        </div>
      </Card>

      {/* Add override */}
      {userId.trim() && (
        <Card>
          <CardTitle>Add Override</CardTitle>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4 items-end">
            <Input
              label="Permission Code"
              value={permissionCode}
              onChange={(e) => setPermissionCode(e.target.value)}
              placeholder="e.g. inventory.write"
            />
            <Select
              label="Override Type"
              value={overrideType}
              onChange={(e) => setOverrideType(e.target.value)}
              options={[
                { value: 'GRANT', label: 'GRANT' },
                { value: 'DENY', label: 'DENY' },
              ]}
            />
            <Button onClick={handleSave} disabled={saveBusy}>
              {saveBusy ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </Card>
      )}

      {/* Overrides table */}
      {userId.trim() && (
        <Card padding={false}>
          <div className="p-5 pb-0">
            <CardTitle>Current Overrides</CardTitle>
          </div>
          <div className="mt-4">
            <DataTable
              columns={columns}
              data={overrides}
              emptyMessage="No permission overrides found for this user."
            />
          </div>
        </Card>
      )}
    </div>
  );
}
