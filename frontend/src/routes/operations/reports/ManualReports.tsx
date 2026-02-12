import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Input, Select } from '@/components/ui/Input';

type DocumentRow = {
  id: number;
  type: string;
  document_number: string | null;
  store_id: number;
  status: string | null;
  occurred_at: string | null;
  user_id: number | null;
  register_id: number | null;
};

const DOC_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'SALES', label: 'Sales' },
  { value: 'RECEIVES', label: 'Receives' },
  { value: 'ADJUSTMENTS', label: 'Adjustments' },
  { value: 'COUNTS', label: 'Counts' },
  { value: 'TRANSFERS', label: 'Transfers' },
  { value: 'RETURNS', label: 'Returns' },
  { value: 'PAYMENTS', label: 'Payments' },
  { value: 'SHIFTS', label: 'Shifts' },
  { value: 'IMPORTS', label: 'Imports' },
  { value: 'DEVICES', label: 'Devices' },
  { value: 'EVENTS', label: 'Events' },
];

function statusVariant(status: string | null): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'muted' {
  if (!status) return 'muted';
  switch (status.toUpperCase()) {
    case 'PENDING': return 'warning';
    case 'APPROVED':
    case 'POSTED':
    case 'COMPLETED': return 'success';
    case 'CANCELLED':
    case 'REJECTED':
    case 'VOIDED': return 'danger';
    case 'IN_TRANSIT': return 'primary';
    default: return 'default';
  }
}

export function ManualReports() {
  const { stores } = useStore();

  const [docType, setDocType] = useState('');
  const [filterStoreId, setFilterStoreId] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (filterStoreId) params.set('store_id', filterStoreId);
      if (docType) params.set('type', docType);
      if (fromDate) {
        const d = new Date(fromDate);
        if (!Number.isNaN(d.getTime())) params.set('from_date', d.toISOString());
      }
      if (toDate) {
        const d = new Date(toDate);
        if (!Number.isNaN(d.getTime())) params.set('to_date', d.toISOString());
      }
      const res = await api.get<{ items: DocumentRow[] }>(`/api/documents?${params}`);
      setDocuments(res.items ?? []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? (err as { detail?: string }).detail ?? err.message : 'Failed to load documents.';
      setError(msg);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [filterStoreId, docType, fromDate, toDate]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  return (
    <div className="flex flex-col gap-6">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <Card>
        <CardTitle>Filters</CardTitle>
        <div className="flex flex-wrap gap-4 items-end mt-4">
          <Select
            label="Store"
            value={filterStoreId}
            onChange={(e) => setFilterStoreId(e.target.value)}
            options={[
              { value: '', label: 'All Managed Stores' },
              ...stores.map((s) => ({ value: String(s.id), label: s.name })),
            ]}
          />
          <Select
            label="Document Type"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            options={DOC_TYPES}
          />
          <Input label="From Date" type="datetime-local" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <Input label="To Date" type="datetime-local" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <Button variant="secondary" onClick={loadDocuments} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </Button>
        </div>
      </Card>

      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Documents</CardTitle>
          <CardDescription>
            {documents.length} document{documents.length !== 1 ? 's' : ''} found.
          </CardDescription>
        </div>
        <div className="mt-4">
          {loading ? (
            <div className="p-5 text-sm text-muted">Loading documents...</div>
          ) : (
            <DataTable
              columns={[
                { key: 'type', header: 'Type', render: (d) => <Badge>{d.type}</Badge> },
                { key: 'document_number', header: 'Doc Number', render: (d) => <span className="font-mono text-xs">{d.document_number ?? '-'}</span> },
                { key: 'store_id', header: 'Store', render: (d) => <span className="text-muted">{stores.find((s) => s.id === d.store_id)?.name ?? `#${d.store_id}`}</span> },
                { key: 'status', header: 'Status', render: (d) => d.status ? <Badge variant={statusVariant(d.status)}>{d.status}</Badge> : <span className="text-muted">-</span> },
                { key: 'occurred_at', header: 'Occurred', render: (d) => <span className="text-muted">{d.occurred_at ? formatDateTime(d.occurred_at) : '-'}</span> },
                { key: 'user_id', header: 'User', render: (d) => <span className="text-muted tabular-nums">{d.user_id != null ? `User #${d.user_id}` : '-'}</span> },
              ]}
              data={documents}
              emptyMessage="No documents match the current filters."
            />
          )}
        </div>
      </Card>
    </div>
  );
}
