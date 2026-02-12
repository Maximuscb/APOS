import { useEffect, useState, useMemo } from 'react';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Input, Select } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';

type StoreConfig = {
  id: number;
  store_id: number;
  key: string;
  value: string | null;
};

type OrgSetting = {
  id: number;
  org_id: number;
  key: string;
  value: string | null;
};

type DeviceSettingRow = {
  id: number;
  device_id: number;
  key: string;
  value: string | null;
};

type RegisterOption = {
  id: number;
  name: string;
  register_number: number;
};

interface SettingDef {
  key: string;
  label: string;
  description: string;
  type: 'text' | 'select' | 'number';
  options?: { value: string; label: string }[];
  defaultValue: string;
}

const APPROVAL_MODE_OPTIONS = [
  { value: 'MANAGER_ONLY', label: 'Manager Only' },
  { value: 'DUAL_AUTH', label: 'Dual Auth' },
];

// Setting definitions for search filtering
const storeSettings: SettingDef[] = [
  { key: 'cash_drawer_approval_mode', label: 'Cash Drawer Approval Mode', description: 'Control how no-sale opens and cash drops are authorized', type: 'select', options: APPROVAL_MODE_OPTIONS, defaultValue: 'MANAGER_ONLY' },
];

const deviceSettings: SettingDef[] = [
  { key: 'auto_logout_minutes', label: 'Auto-Logout Timer', description: 'Minutes of inactivity before automatic logout (0 = disabled)', type: 'number', defaultValue: '0' },
];

export default function SettingsPage() {
  const { currentStoreId: storeId, stores } = useStore();
  const { hasPermission } = useAuth();
  const canManageOrganization = hasPermission('MANAGE_ORGANIZATION');
  const canSwitchStore = hasPermission('MANAGE_STORES') && stores.length > 1;

  const [activeTab, setActiveTab] = useState(canManageOrganization && canSwitchStore ? 'organization' : 'store');
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Store settings
  const [cashDrawerMode, setCashDrawerMode] = useState('MANAGER_ONLY');
  const [selectedStoreId, setSelectedStoreId] = useState(storeId);

  // Organization settings
  const [orgSettings, setOrgSettings] = useState<OrgSetting[]>([]);

  // Device settings
  const [, setDeviceSettingsData] = useState<DeviceSettingRow[]>([]);
  const [registers, setRegisters] = useState<RegisterOption[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [autoLogoutMinutes, setAutoLogoutMinutes] = useState('0');


  // Load store configs
  useEffect(() => {
    if (!selectedStoreId) return;
    setError('');
    setSuccess('');
    api.get<StoreConfig[]>(`/api/stores/${selectedStoreId}/configs`)
      .then((rows) => {
        const approvalMode = rows.find((r) => r.key === 'cash_drawer_approval_mode')?.value;
        setCashDrawerMode((approvalMode ?? 'MANAGER_ONLY').toUpperCase());
      })
      .catch((err: any) => setError(err?.detail ?? 'Failed to load store settings.'));
  }, [selectedStoreId]);

  // Load registers for device tab
  useEffect(() => {
    if (!selectedStoreId) return;
    api.get<RegisterOption[]>(`/api/registers?store_id=${selectedStoreId}`)
      .then((regs) => {
        setRegisters(regs);
        if (regs.length > 0 && !selectedDeviceId) setSelectedDeviceId(regs[0].id);
      })
      .catch(() => {});
  }, [selectedStoreId]);

  // Load device settings when device changes
  useEffect(() => {
    if (!selectedDeviceId) return;
    api.get<DeviceSettingRow[]>(`/api/devices/${selectedDeviceId}/settings`)
      .then((rows) => {
        setDeviceSettingsData(rows);
        const alm = rows.find((r) => r.key === 'auto_logout_minutes')?.value;
        setAutoLogoutMinutes(alm ?? '0');
      })
      .catch(() => {});
  }, [selectedDeviceId]);

  // Load org settings
  useEffect(() => {
    if (!canManageOrganization) return;
    api.get<OrgSetting[]>(`/api/organizations/1/settings`)
      .then(setOrgSettings)
      .catch(() => {});
  }, [canManageOrganization]);

  // Search filter
  const searchLower = search.toLowerCase();
  const matchesSearch = (def: SettingDef) =>
    !search || def.label.toLowerCase().includes(searchLower) || def.description.toLowerCase().includes(searchLower);

  const filteredStoreSettings = useMemo(() => storeSettings.filter(matchesSearch), [search]);
  const filteredDeviceSettings = useMemo(() => deviceSettings.filter(matchesSearch), [search]);

  async function saveStoreConfig(key: string, value: string) {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await api.put(`/api/stores/${selectedStoreId}/configs`, { key, value });
      setSuccess('Setting saved.');
    } catch (err: any) {
      setError(err?.detail ?? 'Failed to save.');
    } finally {
      setSaving(false);
    }
  }

  async function saveDeviceSetting(key: string, value: string) {
    if (!selectedDeviceId) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await api.put(`/api/devices/${selectedDeviceId}/settings`, { key, value });
      setSuccess('Device setting saved.');
    } catch (err: any) {
      setError(err?.detail ?? 'Failed to save.');
    } finally {
      setSaving(false);
    }
  }

  const tabs = [];
  if (canManageOrganization && canSwitchStore) {
    tabs.push({ value: 'organization', label: 'Organization' });
  }
  tabs.push({ value: 'store', label: 'Store' });
  tabs.push({ value: 'device', label: 'Device' });

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-muted mt-1">Configure operational policies and preferences.</p>
      </div>

      {/* Search */}
      <Input
        placeholder="Search settings..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <Tabs tabs={tabs} value={activeTab} onValueChange={setActiveTab} />

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>
      )}

      {/* Organization Tab */}
      {activeTab === 'organization' && (
        <div className="space-y-4">
          {stores.length > 1 && (
            <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
              Organization settings apply to all stores. Changes here affect every location.
            </div>
          )}
          <Card>
            <CardTitle>Organization Settings</CardTitle>
            <CardDescription>Organization-wide configuration. These settings are surfaced in Store Settings when only one store exists.</CardDescription>
            {orgSettings.length === 0 ? (
              <p className="text-sm text-muted mt-3">No organization-level settings configured.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {orgSettings.map((s) => (
                  <div key={s.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <span className="text-sm font-medium">{s.key}</span>
                    <span className="text-sm text-muted">{s.value ?? '(not set)'}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Store Tab */}
      {activeTab === 'store' && (
        <div className="space-y-4">
          {canSwitchStore && (
            <Select
              label="Store"
              value={String(selectedStoreId)}
              onChange={(e) => setSelectedStoreId(Number(e.target.value))}
              options={stores.map((s) => ({ value: String(s.id), label: s.name }))}
            />
          )}

          {filteredStoreSettings.map((def) => (
            <Card key={def.key}>
              <CardTitle>{def.label}</CardTitle>
              <CardDescription>{def.description}</CardDescription>
              <div className="mt-4 max-w-sm">
                {def.type === 'select' && def.options ? (
                  <Select
                    label=""
                    value={cashDrawerMode}
                    onChange={(e) => setCashDrawerMode(e.target.value)}
                    options={def.options}
                  />
                ) : null}
              </div>
              <div className="mt-4">
                <Button onClick={() => saveStoreConfig(def.key, cashDrawerMode)} disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </Card>
          ))}

          {filteredStoreSettings.length === 0 && search && (
            <p className="text-sm text-muted">No store settings match your search.</p>
          )}
        </div>
      )}

      {/* Device Tab */}
      {activeTab === 'device' && (
        <div className="space-y-4">
          {registers.length > 0 ? (
            <>
              <Select
                label="Device"
                value={String(selectedDeviceId ?? '')}
                onChange={(e) => setSelectedDeviceId(Number(e.target.value))}
                options={registers.map((r) => ({ value: String(r.id), label: `${r.name} (#${r.register_number})` }))}
              />

              {filteredDeviceSettings.map((def) => (
                <Card key={def.key}>
                  <CardTitle>{def.label}</CardTitle>
                  <CardDescription>{def.description}</CardDescription>
                  <div className="mt-4 max-w-sm">
                    <Input
                      type="number"
                      value={autoLogoutMinutes}
                      onChange={(e) => setAutoLogoutMinutes(e.target.value)}
                    />
                  </div>
                  <div className="mt-4">
                    <Button onClick={() => saveDeviceSetting(def.key, autoLogoutMinutes)} disabled={saving}>
                      {saving ? 'Saving...' : 'Save'}
                    </Button>
                  </div>
                </Card>
              ))}

              {filteredDeviceSettings.length === 0 && search && (
                <p className="text-sm text-muted">No device settings match your search.</p>
              )}
            </>
          ) : (
            <Card className="p-6 text-center text-muted">
              No devices registered for this store. Create a register first.
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
