import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type Vendor = {
  id: number;
  name: string;
  reorder_mechanism: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  is_active: boolean;
};

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [reorderMechanism, setReorderMechanism] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [deactivatingVendorId, setDeactivatingVendorId] = useState<number | null>(null);

  async function loadVendors(searchTerm = '') {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('include_inactive', 'true');
      if (searchTerm.trim()) params.set('search', searchTerm.trim());
      const res = await api.get<{ items: Vendor[] }>(`/api/vendors?${params.toString()}`);
      setVendors(res.items ?? []);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to load vendors.');
      setVendors([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      loadVendors(search);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [search]);

  async function createVendor() {
    if (!name.trim()) {
      setError('Vendor name is required.');
      return;
    }
    if (!reorderMechanism.trim()) {
      setError('Reorder mechanism is required.');
      return;
    }
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post('/api/vendors', {
        name: name.trim(),
        code: code.trim() || null,
        reorder_mechanism: reorderMechanism.trim(),
        contact_email: contactEmail.trim() || null,
        contact_phone: contactPhone.trim() || null,
      });
      setSuccess('Vendor created.');
      setName('');
      setCode('');
      setReorderMechanism('');
      setContactEmail('');
      setContactPhone('');
      loadVendors(search);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to create vendor.');
    } finally {
      setBusy(false);
    }
  }

  async function deactivateVendor(vendorId: number) {
    setDeactivatingVendorId(vendorId);
    setError('');
    setSuccess('');
    try {
      await api.delete(`/api/vendors/${vendorId}`);
      setSuccess('Vendor deactivated.');
      await loadVendors(search);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to deactivate vendor.');
    } finally {
      setDeactivatingVendorId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Vendors</h1>
        <p className="text-sm text-muted mt-1">Add and manage vendors.</p>
      </div>

      {error && <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>}

      <Card>
        <CardTitle>Add Vendor</CardTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Vendor name" />
          <Input label="Code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Optional" />
          <Input label="Reorder Mechanism" value={reorderMechanism} onChange={(e) => setReorderMechanism(e.target.value)} placeholder="Required (e.g. Send an email)" />
          <Input label="Contact Email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} placeholder="Optional" />
          <Input label="Contact Phone" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="Optional" />
        </div>
        <div className="mt-4">
          <Button onClick={createVendor} disabled={busy}>{busy ? 'Creating...' : 'Create Vendor'}</Button>
        </div>
      </Card>

      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Vendor List</CardTitle>
          <div className="mt-4 max-w-sm">
            <Input
              label="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search vendor name or mechanism"
            />
          </div>
        </div>
        {loading ? (
          <div className="p-5 text-sm text-muted">Loading vendors...</div>
        ) : vendors.length === 0 ? (
          <div className="p-5 text-sm text-muted">No vendors found.</div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 px-5 font-medium">Name</th>
                  <th className="py-2 px-3 font-medium">Reorder Method</th>
                  <th className="py-2 px-3 font-medium">Email</th>
                  <th className="py-2 px-3 font-medium">Phone</th>
                  <th className="py-2 px-5 font-medium">Status</th>
                  <th className="py-2 px-5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} className="border-b border-border/50">
                    <td className="py-2 px-5 font-medium">{v.name}</td>
                    <td className="py-2 px-3 max-w-60 truncate" title={v.reorder_mechanism ?? ''}>{v.reorder_mechanism ?? '-'}</td>
                    <td className="py-2 px-3">{v.contact_email ?? '-'}</td>
                    <td className="py-2 px-3">{v.contact_phone ?? '-'}</td>
                    <td className="py-2 px-5">{v.is_active ? 'Active' : 'Inactive'}</td>
                    <td className="py-2 px-5">
                      <Button
                        size="sm"
                        variant="warning"
                        disabled={!v.is_active || deactivatingVendorId === v.id}
                        onClick={() => deactivateVendor(v.id)}
                      >
                        {deactivatingVendorId === v.id ? 'Deactivating...' : 'Deactivate'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
