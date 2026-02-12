import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';

interface StoreItem {
  id: number;
  name: string;
  code: string | null;
  timezone: string;
  tax_rate_bps: number;
}

interface RegisterItem {
  id: number;
  register_number: number | string;
  name: string;
  store_id: number;
  is_active: boolean;
}

interface UserItem {
  id: number;
  username: string;
  email: string;
  store_id: number | null;
  is_active: boolean;
}

export function OrganizationPage() {
  const { hasPermission, isDeveloper } = useAuth();
  const [activeTab, setActiveTab] = useState('stores');
  const [stores, setStores] = useState<StoreItem[]>([]);
  const [registers, setRegisters] = useState<RegisterItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  // Create store dialog
  const [showCreateStore, setShowCreateStore] = useState(false);
  const [storeName, setStoreName] = useState('');
  const [storeCode, setStoreCode] = useState('');

  const fetchAll = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.get<StoreItem[]>('/api/stores'),
      api.get<{ users: UserItem[] }>('/api/admin/users'),
    ])
      .then(([s, u]) => {
        setStores(s);
        setUsers(u.users ?? []);
        // Fetch registers for all stores
        if (s.length > 0) {
          Promise.all(s.map((store) => api.get<RegisterItem[]>(`/api/registers?store_id=${store.id}`).catch(() => [] as RegisterItem[])))
            .then((allRegs) => setRegisters(allRegs.flat()));
        }
      })
      .catch((e: any) => {
        setError(e?.detail || e?.message || 'Failed to load organization data.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreateStore = async () => {
    if (!storeName.trim()) return;
    setCreateError(null);
    try {
      await api.post('/api/stores', { name: storeName, code: storeCode || undefined });
      setShowCreateStore(false);
      setStoreName('');
      setStoreCode('');
      fetchAll();
    } catch (e: any) {
      setCreateError(e?.detail || e?.message || 'Failed to create store.');
    }
  };

  const canCreateStore = isDeveloper || hasPermission('MANAGE_STORES');

  const tabs = [
    { value: 'stores', label: `Stores (${stores.length})` },
    { value: 'devices', label: `Devices (${registers.length})` },
    { value: 'users', label: `Users (${users.length})` },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Organization</h1>
        {activeTab === 'stores' && canCreateStore && (
          <Button onClick={() => setShowCreateStore(true)}>+ New Store</Button>
        )}
      </div>

      <Tabs tabs={tabs} value={activeTab} onValueChange={setActiveTab} />
      {error && <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm">{error}</div>}

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : activeTab === 'stores' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {stores.map((s) => (
            <Card key={s.id} className="p-4">
              <h3 className="font-semibold text-slate-900">{s.name}</h3>
              {s.code && <p className="text-sm text-muted">Code: {s.code}</p>}
              <div className="flex gap-4 mt-2 text-xs text-muted">
                <span>TZ: {s.timezone}</span>
                <span>Tax: {(s.tax_rate_bps / 100).toFixed(2)}%</span>
              </div>
            </Card>
          ))}
        </div>
      ) : activeTab === 'devices' ? (
        <div className="space-y-4">
          {stores.map((store) => {
            const storeRegs = registers.filter((r) => r.store_id === store.id);
            if (storeRegs.length === 0) return null;
            return (
              <div key={store.id}>
                <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-2">{store.name}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {storeRegs.map((r) => (
                    <Card key={r.id} className="p-3 flex items-center justify-between">
                      <div>
                        <span className="font-medium text-sm">{r.name}</span>
                        <span className="text-xs text-muted ml-2">#{r.register_number}</span>
                      </div>
                      <Badge variant={r.is_active ? 'primary' : 'default'}>{r.is_active ? 'Active' : 'Inactive'}</Badge>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
          {registers.length === 0 && <p className="text-muted text-sm">No devices registered.</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {users.length === 0 && <p className="text-muted text-sm">No users found.</p>}
          {users.map((u) => (
            <Card key={u.id} className="p-3 flex items-center justify-between">
              <div>
                <span className="font-medium text-sm">{u.username}</span>
                <span className="text-xs text-muted ml-2">{u.email}</span>
              </div>
              <div className="flex items-center gap-2">
                {u.store_id && (
                  <span className="text-xs text-muted">Store #{u.store_id}</span>
                )}
                <Badge variant={u.is_active ? 'primary' : 'default'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreateStore} onClose={() => setShowCreateStore(false)} title="New Store">
        <div className="space-y-4 p-1">
          {createError && <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm">{createError}</div>}
          <Input label="Store Name" value={storeName} onChange={(e) => setStoreName(e.target.value)} />
          <Input label="Store Code (optional)" value={storeCode} onChange={(e) => setStoreCode(e.target.value)} />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreateStore(false)}>Cancel</Button>
            <Button onClick={handleCreateStore}>Create</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
