import { useMemo, useState, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input, Select } from '@/components/ui/Input';

type ImportBatch = {
  id: number;
  status: string;
  import_type: string;
  staged_rows?: number;
  mapped_rows?: number;
  posted_rows?: number;
  error_rows?: number;
  quarantined_rows?: number;
  total_rows?: number;
};

type StagingRow = {
  id: number;
  row_number: number;
  mapping_status: string;
  posting_status: string;
  error_message: string | null;
  unmapped_references: string | null;
  normalized_data: Record<string, unknown> | null;
};

type UnmappedDetail = {
  row_number: number;
  field: string;
  entity_type: string;
  value: string;
};

export default function ImportsPage() {
  const [importType, setImportType] = useState('Products');
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<StagingRow[]>([]);
  const [unmappedDetails, setUnmappedDetails] = useState<UnmappedDetail[]>([]);
  const [busy, setBusy] = useState(false);
  const [postingBusy, setPostingBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [postProgress, setPostProgress] = useState({ processed: 0, posted: 0, errors: 0 });
  const [mappingEntityType, setMappingEntityType] = useState('PRODUCT');
  const [mappingForeignId, setMappingForeignId] = useState('');
  const [mappingLocalId, setMappingLocalId] = useState('');

  const summary = useMemo(() => {
    const mapped = rows.filter((r) => r.mapping_status === 'READY').length;
    const unmapped = rows.filter((r) => r.mapping_status === 'UNMAPPED').length;
    const errors = rows.filter((r) => r.mapping_status === 'ERROR' || r.posting_status === 'ERROR').length;
    const posted = rows.filter((r) => r.posting_status === 'POSTED').length;
    return { total: rows.length, mapped, unmapped, errors, posted };
  }, [rows]);

  async function createBatch() {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.post<{ batch: ImportBatch }>('/api/imports/batches', { import_type: importType });
      setBatch(res.batch);
      setRows([]);
      setUnmappedDetails([]);
      setSuccess(`Batch #${res.batch.id} created.`);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to create batch.');
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile() {
    if (!batch || !file) {
      setError('Create a batch and select a file first.');
      return;
    }
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const token = api.getToken();
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`/api/imports/batches/${batch.id}/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error || body?.detail || `HTTP ${res.status}`);
      }
      setSuccess('File uploaded and staged.');
      setFile(null);
      await refreshAll();
    } catch (err: any) {
      setError(err?.message ?? 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }

  async function refreshAll() {
    if (!batch) return;
    const [statusRes, rowRes, unmappedRes] = await Promise.all([
      api.get<{ batch: ImportBatch }>(`/api/imports/batches/${batch.id}/status`),
      api.get<{ rows: StagingRow[] }>(`/api/imports/batches/${batch.id}/rows?per_page=500`),
      api.get<{ details: UnmappedDetail[] }>(`/api/imports/batches/${batch.id}/unmapped`).catch(() => ({ details: [] })),
    ]);
    setBatch(statusRes.batch);
    setRows(rowRes.rows ?? []);
    setUnmappedDetails(unmappedRes.details ?? []);
  }

  async function applyMapping() {
    if (!batch || !mappingEntityType || !mappingForeignId || !mappingLocalId) return;
    setBusy(true);
    setError('');
    try {
      await api.post(`/api/imports/batches/${batch.id}/mappings`, {
        entity_type: mappingEntityType.toLowerCase(),
        foreign_id: mappingForeignId,
        local_entity_id: Number(mappingLocalId),
      });
      setSuccess('Mapping saved.');
      setMappingForeignId('');
      setMappingLocalId('');
      await refreshAll();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to set mapping.');
    } finally {
      setBusy(false);
    }
  }

  async function postBatch() {
    if (!batch) return;
    setPostingBusy(true);
    setError('');
    setSuccess('');
    setPostProgress({ processed: 0, posted: 0, errors: 0 });
    try {
      let keepGoing = true;
      while (keepGoing) {
        const res = await api.post<{ processed: number; posted: number; errors: number }>(
          `/api/imports/batches/${batch.id}/post?limit=200`,
          {},
        );
        setPostProgress((prev) => ({
          processed: prev.processed + (res.processed || 0),
          posted: prev.posted + (res.posted || 0),
          errors: prev.errors + (res.errors || 0),
        }));
        if (!res.processed || res.processed === 0) keepGoing = false;
      }
      await refreshAll();
      setSuccess('Posting completed or paused (no more READY rows).');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to post batch.');
    } finally {
      setPostingBusy(false);
    }
  }

  function statusVariant(status: string) {
    switch ((status || '').toUpperCase()) {
      case 'COMPLETED':
      case 'POSTED':
      case 'READY':
        return 'success' as const;
      case 'ERROR':
      case 'FAILED':
        return 'danger' as const;
      case 'UNMAPPED':
      case 'POSTING':
      case 'MAPPING':
        return 'warning' as const;
      default:
        return 'default' as const;
    }
  }

  const progressPct = summary.total > 0 ? Math.min(100, Math.round((summary.posted / summary.total) * 100)) : 0;

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Imports</h1>
        <p className="text-sm text-muted mt-1">
          Create a batch, upload, validate, resolve mappings, and post into canonical tables.
        </p>
      </div>

      {error && <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>}

      <Card>
        <CardTitle>1. Create Batch</CardTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
          <Select
            label="Import Type"
            value={importType}
            onChange={(e) => setImportType(e.target.value)}
            options={[
              { value: 'Products', label: 'Products' },
              { value: 'Inventory', label: 'Inventory' },
              { value: 'Sales', label: 'Sales' },
            ]}
          />
        </div>
        <div className="mt-4 flex gap-2">
          <Button onClick={createBatch} disabled={busy}>Create Batch</Button>
          {batch && <Button variant="secondary" onClick={refreshAll} disabled={busy}>Refresh</Button>}
        </div>
      </Card>

      {batch && (
        <Card>
          <CardTitle>2. Upload CSV/JSON/XLSX</CardTitle>
          <p className="text-sm text-muted mt-1">Batch #{batch.id} ({batch.import_type})</p>
          <div className="mt-4 flex flex-col gap-3">
            <input
              type="file"
              accept=".csv,.json,.xlsx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="h-11 px-3 py-2 rounded-xl border border-border bg-white text-sm file:mr-3 file:px-3 file:py-1 file:rounded-lg file:border-0 file:bg-primary/10 file:text-primary file:text-sm file:font-medium file:cursor-pointer"
            />
            <div className="flex gap-2">
              <Button onClick={uploadFile} disabled={busy || !file}>Upload & Stage</Button>
            </div>
          </div>
        </Card>
      )}

      {batch && (
        <Card>
          <CardTitle>3. Preview Summary</CardTitle>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mt-4">
            <Summary label="Batch Status" value={<Badge variant={statusVariant(batch.status)}>{batch.status}</Badge>} />
            <Summary label="Total" value={String(summary.total || batch.total_rows || 0)} />
            <Summary label="Ready" value={String(summary.mapped || batch.mapped_rows || 0)} />
            <Summary label="Unmapped" value={String(summary.unmapped)} />
            <Summary label="Errors" value={String(summary.errors || batch.error_rows || 0)} />
            <Summary label="Posted" value={String(summary.posted || batch.posted_rows || 0)} />
          </div>
        </Card>
      )}

      {batch && (
        <Card>
          <CardTitle>4. Mapping Resolution</CardTitle>
          <p className="text-sm text-muted mt-1">Resolve unmapped references before posting.</p>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
            <Select
              label="Entity Type"
              value={mappingEntityType}
              onChange={(e) => setMappingEntityType(e.target.value)}
              options={[
                { value: 'PRODUCT', label: 'PRODUCT' },
                { value: 'USER', label: 'USER' },
                { value: 'REGISTER', label: 'REGISTER' },
                { value: 'STORE', label: 'STORE' },
              ]}
            />
            <Input label="Foreign ID" value={mappingForeignId} onChange={(e) => setMappingForeignId(e.target.value)} />
            <Input label="Local ID" value={mappingLocalId} onChange={(e) => setMappingLocalId(e.target.value)} />
            <div className="flex items-end">
              <Button onClick={applyMapping} disabled={busy || !mappingForeignId || !mappingLocalId}>Add Mapping</Button>
            </div>
          </div>
          <div className="mt-4 max-h-52 overflow-auto rounded-xl border border-border">
            {unmappedDetails.length === 0 ? (
              <div className="p-3 text-sm text-muted">No unmapped references.</div>
            ) : (
              unmappedDetails.map((d, i) => (
                <div key={`${d.row_number}-${d.field}-${i}`} className="px-3 py-2 text-sm border-b border-border last:border-b-0">
                  Row {d.row_number}: <span className="font-medium">{d.entity_type}</span> `{d.value}` in `{d.field}`
                </div>
              ))
            )}
          </div>
        </Card>
      )}

      {batch && (
        <Card>
          <CardTitle>5. Post Batch</CardTitle>
          <div className="mt-4 flex items-center gap-3">
            <Button onClick={postBatch} disabled={postingBusy || summary.mapped === 0}>Post Ready Rows</Button>
            <span className="text-sm text-muted">
              Processed: {postProgress.processed} | Posted: {postProgress.posted} | Errors: {postProgress.errors}
            </span>
          </div>
          <div className="mt-3 h-3 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-primary transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <p className="text-xs text-muted mt-1">{progressPct}% posted</p>
        </Card>
      )}

      {batch && (
        <Card>
          <CardTitle>6. Completion</CardTitle>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <Summary label="Posted" value={String(batch.posted_rows ?? 0)} />
            <Summary label="Errors" value={String(batch.error_rows ?? 0)} />
            <Summary label="Quarantined" value={String(batch.quarantined_rows ?? 0)} />
            <Summary label="Final Status" value={<Badge variant={statusVariant(batch.status)}>{batch.status}</Badge>} />
          </div>
        </Card>
      )}
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string | ReactNode }) {
  return (
    <div>
      <p className="text-xs text-muted font-medium uppercase tracking-wider">{label}</p>
      <div className="text-sm font-semibold mt-1">{value}</div>
    </div>
  );
}
