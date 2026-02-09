import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type Vendor = {
  id: number;
  name: string;
  code: string | null;
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
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [busy, setBusy] = useState(false);

  async function loadVendors() {
    setLoading(true);
    try {
      const res = await api.get<{ items: Vendor[] }>('/api/vendors');
      setVendors(res.items ?? []);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to load vendors.');
      setVendors([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadVendors();
  }, []);

  async function createVendor() {
    if (!name.trim()) {
      setError('Vendor name is required.');
      return;
    }
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post('/api/vendors', {
        name: name.trim(),
        code: code.trim() || null,
        contact_email: contactEmail.trim() || null,
        contact_phone: contactPhone.trim() || null,
      });
      setSuccess('Vendor created.');
      setName('');
      setCode('');
      setContactEmail('');
      setContactPhone('');
      loadVendors();
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to create vendor.');
    } finally {
      setBusy(false);
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
          <Input label="Contact Email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} placeholder="Optional" />
          <Input label="Contact Phone" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="Optional" />
        </div>
        <div className="mt-4">
          <Button onClick={createVendor} disabled={busy}>{busy ? 'Creating...' : 'Create Vendor'}</Button>
        </div>
      </Card>

      <Card padding={false}>
        <div className="p-5 pb-0"><CardTitle>Vendor List</CardTitle></div>
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
                  <th className="py-2 px-3 font-medium">Code</th>
                  <th className="py-2 px-3 font-medium">Email</th>
                  <th className="py-2 px-3 font-medium">Phone</th>
                  <th className="py-2 px-5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} className="border-b border-border/50">
                    <td className="py-2 px-5 font-medium">{v.name}</td>
                    <td className="py-2 px-3">{v.code ?? '-'}</td>
                    <td className="py-2 px-3">{v.contact_email ?? '-'}</td>
                    <td className="py-2 px-3">{v.contact_phone ?? '-'}</td>
                    <td className="py-2 px-5">{v.is_active ? 'Active' : 'Inactive'}</td>
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
