import { useEffect, useMemo, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Input, Select } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';

type RegistryItem = {
  key: string;
  scope_allowed: string[];
  type: string;
  default_value_json: any;
  validation_json: Record<string, any>;
  description: string;
  category: string;
  subcategory: string | null;
  is_sensitive: boolean;
  is_developer_only: boolean;
  requires_restart: boolean;
  requires_reprice: boolean;
  requires_recalc: boolean;
  min_role_to_view: string | null;
  min_role_to_edit: string | null;
};

type ScopeSettingItem = {
  key: string;
  scope_type: 'ORG' | 'STORE' | 'DEVICE' | 'USER';
  scope_id: number;
  value_json: any;
  effective_value_json: any;
  effective_source: string;
  inherited: boolean;
  registry: RegistryItem;
};

type ScopeResponse = {
  scope_type: 'ORG' | 'STORE' | 'DEVICE' | 'USER';
  scope_id: number;
  org_id: number;
  items: ScopeSettingItem[];
};

type RegisterOption = {
  id: number;
  name: string;
  register_number: string;
  store_id: number;
};

function formatValue(v: any) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function getInputType(valueType: string): 'text' | 'number' | 'json' | 'enum' | 'bool' {
  if (valueType === 'bool') return 'bool';
  if (valueType === 'enum') return 'enum';
  if (valueType === 'json') return 'json';
  if (['int', 'decimal', 'decimal_cents', 'duration_seconds'].includes(valueType)) return 'number';
  return 'text';
}

export default function SettingsPage() {
  const { currentStoreId, stores, setStoreId } = useStore();
  const { user, hasPermission, isDeveloper } = useAuth();

  const canViewOrg = hasPermission('VIEW_ORGANIZATION') || hasPermission('MANAGE_ORGANIZATION') || isDeveloper;
  const canEditOrg = hasPermission('MANAGE_ORGANIZATION') || hasPermission('SYSTEM_ADMIN') || isDeveloper;
  const canEditStore = hasPermission('MANAGE_STORES') || hasPermission('SYSTEM_ADMIN') || isDeveloper;
  const canEditDevice = hasPermission('MANAGE_DEVICE_SETTINGS') || hasPermission('SYSTEM_ADMIN') || isDeveloper;

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [scopeTab, setScopeTab] = useState<'organization' | 'store' | 'device' | 'user'>(
    canViewOrg && stores.length > 1 ? 'organization' : 'store',
  );
  const [scopeData, setScopeData] = useState<ScopeResponse | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [selectedStoreId, setSelectedStoreId] = useState<number>(currentStoreId);
  const [registers, setRegisters] = useState<RegisterOption[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);

  useEffect(() => {
    setSelectedStoreId(currentStoreId);
  }, [currentStoreId]);

  useEffect(() => {
    if (scopeTab !== 'device' || !selectedStoreId) return;
    api.get<{ registers: RegisterOption[] }>(`/api/registers?store_id=${selectedStoreId}`)
      .then((res) => {
        const list = res.registers ?? [];
        setRegisters(list);
        if (list.length > 0) setSelectedDeviceId((prev) => prev ?? list[0].id);
      })
      .catch(() => {
        setRegisters([]);
        setSelectedDeviceId(null);
      });
  }, [scopeTab, selectedStoreId]);

  async function loadScope() {
    setError('');
    setSuccess('');
    try {
      if (scopeTab === 'organization') {
        if (!canViewOrg || stores.length === 0) {
          setScopeData(null);
          return;
        }
        const org = await api.get<ScopeResponse>('/api/settings/org/current');
        setScopeData(org);
      } else if (scopeTab === 'store') {
        const store = await api.get<ScopeResponse>(`/api/settings/store/${selectedStoreId}`);
        setScopeData(store);
      } else if (scopeTab === 'device') {
        if (!selectedDeviceId) {
          setScopeData(null);
          return;
        }
        const device = await api.get<ScopeResponse>(`/api/settings/device/${selectedDeviceId}`);
        setScopeData(device);
      } else {
        const me = await api.get<ScopeResponse>(`/api/settings/user/${user?.id}`);
        setScopeData(me);
      }
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to load scoped settings.');
      setScopeData(null);
    }
  }

  useEffect(() => {
    loadScope();
  }, [scopeTab, selectedStoreId, selectedDeviceId, user?.id]);

  useEffect(() => {
    if (!scopeData) return;
    const next: Record<string, string> = {};
    for (const item of scopeData.items) {
      const base = item.value_json ?? item.effective_value_json;
      next[item.key] = formatValue(base);
    }
    setDraft(next);
  }, [scopeData?.scope_type, scopeData?.scope_id, scopeData?.items?.length]);

  const categories = useMemo(() => {
    const set = new Set((scopeData?.items ?? []).map((i) => i.registry.category));
    return Array.from(set).sort();
  }, [scopeData?.items]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (scopeData?.items ?? []).filter((item) => {
      if (category && item.registry.category !== category) return false;
      if (!q) return true;
      return (
        item.key.toLowerCase().includes(q)
        || (item.registry.description || '').toLowerCase().includes(q)
        || (item.registry.subcategory || '').toLowerCase().includes(q)
      );
    });
  }, [scopeData?.items, search, category]);

  function canEditItem(item: ScopeSettingItem) {
    if (scopeTab === 'organization') return canEditOrg;
    if (scopeTab === 'store') return canEditStore;
    if (scopeTab === 'device') return canEditDevice;
    return item.scope_id === user?.id || hasPermission('EDIT_USER') || isDeveloper;
  }

  function parseDraftValue(item: ScopeSettingItem, raw: string): any {
    const t = getInputType(item.registry.type);
    if (t === 'bool') return raw === 'true';
    if (t === 'number') return raw.trim() === '' ? null : Number(raw);
    if (t === 'json') return raw.trim() === '' ? null : JSON.parse(raw);
    return raw;
  }

  async function saveItem(item: ScopeSettingItem) {
    const pathBase =
      item.scope_type === 'ORG' ? `/api/settings/org/${item.scope_id}`
        : item.scope_type === 'STORE' ? `/api/settings/store/${item.scope_id}`
          : item.scope_type === 'DEVICE' ? `/api/settings/device/${item.scope_id}`
            : `/api/settings/user/${item.scope_id}`;
    setBusyKey(item.key);
    setError('');
    setSuccess('');
    try {
      const value_json = parseDraftValue(item, draft[item.key] ?? '');
      const res = await api.patch<{ errors?: Array<{ key: string; error: string }> }>(pathBase, {
        updates: [{ key: item.key, value_json }],
      });
      if (Array.isArray(res.errors) && res.errors.length > 0) {
        throw new Error(res.errors[0].error || 'Failed to save setting.');
      }
      setSuccess(`Saved ${item.key}`);
      await loadScope();
    } catch (e: any) {
      setError(e?.detail || e?.message || `Failed to save ${item.key}.`);
    } finally {
      setBusyKey(null);
    }
  }

  async function clearOverride(item: ScopeSettingItem) {
    const pathBase =
      item.scope_type === 'ORG' ? `/api/settings/org/${item.scope_id}`
        : item.scope_type === 'STORE' ? `/api/settings/store/${item.scope_id}`
          : item.scope_type === 'DEVICE' ? `/api/settings/device/${item.scope_id}`
            : `/api/settings/user/${item.scope_id}`;
    setBusyKey(item.key);
    setError('');
    setSuccess('');
    try {
      const res = await api.patch<{ errors?: Array<{ key: string; error: string }> }>(pathBase, {
        updates: [{ key: item.key, unset: true }],
      });
      if (Array.isArray(res.errors) && res.errors.length > 0) {
        throw new Error(res.errors[0].error || 'Failed to clear override.');
      }
      setSuccess(`Cleared ${item.key}`);
      await loadScope();
    } catch (e: any) {
      setError(e?.detail || e?.message || `Failed to clear ${item.key}.`);
    } finally {
      setBusyKey(null);
    }
  }

  const topTabs = [
    ...(canViewOrg && stores.length > 1 ? [{ value: 'organization', label: 'Organization' }] : []),
    { value: 'store', label: 'Store' },
    { value: 'device', label: 'Device' },
    { value: 'user', label: 'User' },
  ];

  return (
    <div className="flex flex-col gap-5 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-muted mt-1">Unified configuration with precedence: USER &gt; DEVICE &gt; STORE &gt; ORG &gt; SYSTEM DEFAULT.</p>
      </div>

      {scopeTab === 'organization' && stores.length > 1 && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
          Changes at Organization scope can impact all stores.
        </div>
      )}
      {scopeTab === 'device' && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800">
          Some device settings require app/device restart before taking effect.
        </div>
      )}

      <Tabs tabs={topTabs} value={scopeTab} onValueChange={(v) => setScopeTab(v as any)} />

      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(scopeTab === 'store' || scopeTab === 'device') && (
            <Select
              label="Store"
              value={String(selectedStoreId)}
              onChange={(e) => {
                const next = Number(e.target.value);
                setSelectedStoreId(next);
                if (scopeTab !== 'device') setStoreId(next);
              }}
              options={stores.map((s) => ({ value: String(s.id), label: s.name }))}
            />
          )}
          {scopeTab === 'device' && (
            <Select
              label="Device"
              value={String(selectedDeviceId ?? '')}
              onChange={(e) => setSelectedDeviceId(Number(e.target.value))}
              options={(registers ?? []).map((r) => ({ value: String(r.id), label: `${r.name} (#${r.register_number})` }))}
            />
          )}
          <Input label="Search" placeholder="Search by key or description" value={search} onChange={(e) => setSearch(e.target.value)} />
          <Select
            label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={[{ value: '', label: 'All categories' }, ...categories.map((c) => ({ value: c, label: c }))]}
          />
        </div>
      </Card>

      {error && <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>}

      {scopeData && filteredItems.length === 0 && (
        <Card>
          <p className="text-sm text-muted">No settings matched your filters.</p>
        </Card>
      )}

      {filteredItems.map((item) => {
        const inputType = getInputType(item.registry.type);
        const options = item.registry.validation_json?.enum as string[] | undefined;
        const canEdit = canEditItem(item);
        return (
          <Card key={item.key}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">{item.key}</CardTitle>
                <CardDescription>{item.registry.description || 'No description provided.'}</CardDescription>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant={item.inherited ? 'muted' : 'primary'}>
                    {item.inherited ? 'Inherited' : 'Override'}
                  </Badge>
                  <Badge variant="muted">{item.effective_source}</Badge>
                  {item.registry.requires_restart && <Badge variant="warning">Restart Required</Badge>}
                  {item.registry.requires_reprice && <Badge variant="warning">Reprice Impact</Badge>}
                  {item.registry.requires_recalc && <Badge variant="warning">Recalc Impact</Badge>}
                </div>
              </div>
              <div className="text-xs text-muted">
                <div>{item.registry.category}</div>
                <div>{item.registry.subcategory || '-'}</div>
              </div>
            </div>

            <div className="mt-4">
              {inputType === 'bool' && (
                <Select
                  label="Value"
                  value={(draft[item.key] ?? String(Boolean(item.value_json ?? item.effective_value_json))) as string}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [item.key]: e.target.value }))}
                  options={[{ value: 'true', label: 'True' }, { value: 'false', label: 'False' }]}
                  disabled={!canEdit}
                />
              )}
              {inputType === 'enum' && (
                <Select
                  label="Value"
                  value={draft[item.key] ?? String(item.value_json ?? item.effective_value_json ?? '')}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [item.key]: e.target.value }))}
                  options={(options ?? []).map((v) => ({ value: v, label: v }))}
                  disabled={!canEdit}
                />
              )}
              {inputType === 'json' && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">Value (JSON)</label>
                  <textarea
                    className="min-h-32 px-3 py-2 rounded-xl border border-border bg-white text-sm focus:outline-2 focus:outline-primary"
                    value={draft[item.key] ?? ''}
                    onChange={(e) => setDraft((prev) => ({ ...prev, [item.key]: e.target.value }))}
                    disabled={!canEdit}
                  />
                </div>
              )}
              {inputType !== 'bool' && inputType !== 'enum' && inputType !== 'json' && (
                <Input
                  label="Value"
                  type={inputType === 'number' ? 'number' : 'text'}
                  value={draft[item.key] ?? ''}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [item.key]: e.target.value }))}
                  disabled={!canEdit}
                />
              )}
            </div>

            <div className="mt-4 flex gap-2">
              <Button size="sm" onClick={() => saveItem(item)} disabled={!canEdit || busyKey === item.key}>
                {busyKey === item.key ? 'Saving...' : 'Override Here'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => clearOverride(item)} disabled={!canEdit || item.inherited || busyKey === item.key}>
                Clear Override
              </Button>
            </div>
          </Card>
        );
      })}

      {stores.length <= 1 && scopeTab === 'store' && canViewOrg && (
        <Card>
          <CardTitle>Organization Scope in Single-Store Mode</CardTitle>
          <CardDescription>
            This organization has a single store. Organization settings are still stored at ORG scope and can be managed from this page.
          </CardDescription>
          <div className="mt-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setScopeTab('organization')}
              disabled={!canViewOrg}
            >
              Open Organization Settings
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
