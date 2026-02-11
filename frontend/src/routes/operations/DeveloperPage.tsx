import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { api } from '@/lib/api';

interface DevOrg {
  id: number;
  name: string;
  code: string | null;
  is_active: boolean;
}

interface DevStatus {
  is_developer: boolean;
  user_id: number;
  username: string;
  org_id: number | null;
  org_name: string | null;
  store_id: number | null;
}

type JsonRecord = Record<string, unknown> | unknown[] | null;

function getErrorMessage(e: any, fallback: string) {
  return e?.detail || e?.message || fallback;
}

export function DeveloperPage() {
  const { isDeveloper, switchOrg } = useAuth();
  const [orgs, setOrgs] = useState<DevOrg[]>([]);
  const [status, setStatus] = useState<DevStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [orgName, setOrgName] = useState('');
  const [orgCode, setOrgCode] = useState('');
  const [initialStoreName, setInitialStoreName] = useState('');
  const [busy, setBusy] = useState(false);

  const [endpointResponse, setEndpointResponse] = useState<JsonRecord>(null);
  const [endpointError, setEndpointError] = useState<string | null>(null);

  const currentOrgName = useMemo(() => {
    if (!status?.org_id) return 'No org selected';
    return status.org_name ?? `Org #${status.org_id}`;
  }, [status]);

  async function loadDeveloperData() {
    if (!isDeveloper) return;
    setLoading(true);
    setError(null);
    try {
      const [orgRes, statusRes] = await Promise.all([
        api.get<DevOrg[]>('/api/developer/organizations'),
        api.get<DevStatus>('/api/developer/status'),
      ]);
      setOrgs(orgRes);
      setStatus(statusRes);
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to load developer data.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDeveloperData();
  }, [isDeveloper]);

  async function handleCreateOrg() {
    if (!orgName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.post('/api/developer/organizations', {
        name: orgName.trim(),
        code: orgCode.trim() || undefined,
        initial_store_name: initialStoreName.trim() || undefined,
      });
      setOrgName('');
      setOrgCode('');
      setInitialStoreName('');
      await loadDeveloperData();
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to create organization.'));
    } finally {
      setBusy(false);
    }
  }

  async function runEndpoint(path: string, method: 'GET' | 'POST', body?: Record<string, unknown>) {
    setEndpointError(null);
    setEndpointResponse(null);
    try {
      if (method === 'GET') {
        const res = await api.get<JsonRecord>(path);
        setEndpointResponse(res);
      } else {
        const res = await api.post<JsonRecord>(path, body ?? {});
        setEndpointResponse(res);
      }
    } catch (e: any) {
      setEndpointError(getErrorMessage(e, `Endpoint call failed: ${path}`));
    }
  }

  if (!isDeveloper) {
    return (
      <div className="p-6">
        <Card>
          <CardTitle>Developer Access Required</CardTitle>
          <CardDescription>This screen is only available to developer users.</CardDescription>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-slate-900">Developer Dashboard</h1>
        <Button variant="secondary" onClick={loadDeveloperData} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      {error && <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm">{error}</div>}

      <Card className="space-y-3">
        <div>
          <CardTitle>Current Context</CardTitle>
          <CardDescription>Current org and store context from your developer session.</CardDescription>
        </div>
        <div className="text-sm grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-xl border border-border p-3">
            <p className="text-xs text-muted">Organization</p>
            <p className="font-semibold text-slate-900">{currentOrgName}</p>
          </div>
          <div className="rounded-xl border border-border p-3">
            <p className="text-xs text-muted">Org ID</p>
            <p className="font-semibold text-slate-900">{status?.org_id ?? '--'}</p>
          </div>
          <div className="rounded-xl border border-border p-3">
            <p className="text-xs text-muted">Store ID</p>
            <p className="font-semibold text-slate-900">{status?.store_id ?? '--'}</p>
          </div>
        </div>
      </Card>

      <Card className="space-y-3">
        <div>
          <CardTitle>Create Organization</CardTitle>
          <CardDescription>Create a new organization and optional initial store.</CardDescription>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input label="Organization Name" value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Acme Retail Group" />
          <Input label="Code (optional)" value={orgCode} onChange={(e) => setOrgCode(e.target.value)} placeholder="ACME" />
          <Input label="Initial Store (optional)" value={initialStoreName} onChange={(e) => setInitialStoreName(e.target.value)} placeholder="Main Store" />
        </div>
        <div className="flex justify-end">
          <Button onClick={handleCreateOrg} disabled={busy || !orgName.trim()}>
            {busy ? 'Creating...' : 'Create Organization'}
          </Button>
        </div>
      </Card>

      <Card className="space-y-3">
        <div>
          <CardTitle>Switch Organization</CardTitle>
          <CardDescription>Switch your developer session into a target organization.</CardDescription>
        </div>
        <div className="space-y-2">
          {orgs.length === 0 && <p className="text-sm text-muted">No organizations found.</p>}
          {orgs.map((org) => (
            <div key={org.id} className="rounded-xl border border-border p-3 flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-900">{org.name}</p>
                <p className="text-xs text-muted">
                  {`Org #${org.id}${org.code ? ` - ${org.code}` : ''}${org.is_active ? '' : ' - inactive'}`}
                </p>
              </div>
              <Button
                variant="secondary"
                onClick={async () => {
                  await switchOrg(org.id);
                  window.location.reload();
                }}
                disabled={status?.org_id === org.id}
              >
                {status?.org_id === org.id ? 'Current' : 'Switch'}
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-3">
        <div>
          <CardTitle>Developer Endpoints</CardTitle>
          <CardDescription>Run key developer endpoint calls directly from UI.</CardDescription>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="secondary" onClick={() => runEndpoint('/api/developer/status', 'GET')}>GET /api/developer/status</Button>
          <Button variant="secondary" onClick={() => runEndpoint('/api/developer/organizations', 'GET')}>GET /api/developer/organizations</Button>
          {status?.org_id && (
            <Button variant="secondary" onClick={() => runEndpoint('/api/developer/switch-org', 'POST', { org_id: status.org_id })}>
              POST /api/developer/switch-org
            </Button>
          )}
        </div>
        {endpointError && <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm">{endpointError}</div>}
        {endpointResponse !== null && (
          <pre className="text-xs bg-slate-900 text-slate-100 rounded-xl p-3 overflow-auto max-h-72">
            {JSON.stringify(endpointResponse, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}

export default DeveloperPage;
