import { useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ImportBatch = {
  id: number;
  status: string;
  import_type: string;
  staged_rows?: number;
  posted_rows?: number;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ImportsPage() {
  const [importType, setImportType] = useState('Products');
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function createBatch() {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.post<{ batch: ImportBatch }>('/api/imports/batches', {
        import_type: importType,
      });
      setBatch(res.batch);
      setSuccess(`Batch #${res.batch.id} created. Upload a file to stage rows.`);
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
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body?.error) detail = body.error;
          else if (body?.detail) detail = body.detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      setSuccess('File uploaded successfully.');
      setFile(null);
      refreshStatus();
    } catch (err: any) {
      setError(err?.message ?? 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }

  async function refreshStatus() {
    if (!batch) return;
    setBusy(true);
    setError('');
    try {
      const res = await api.get<{ batch: ImportBatch }>(
        `/api/imports/batches/${batch.id}/status`,
      );
      setBatch(res.batch);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to refresh status.');
    } finally {
      setBusy(false);
    }
  }

  function statusVariant(status: string) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'posted':
        return 'success' as const;
      case 'error':
      case 'failed':
        return 'danger' as const;
      case 'staging':
      case 'processing':
        return 'warning' as const;
      default:
        return 'default' as const;
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Imports</h1>
        <p className="text-sm text-muted mt-1">
          Import products, sales, or inventory data from CSV, JSON, or Excel files.
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

      {/* Create Batch */}
      <Card>
        <CardTitle>Create Import Batch</CardTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
          <Select
            label="Import Type"
            value={importType}
            onChange={(e) => setImportType(e.target.value)}
            options={[
              { value: 'Products', label: 'Products' },
              { value: 'Sales', label: 'Sales' },
              { value: 'Inventory', label: 'Inventory' },
            ]}
          />
        </div>
        <div className="mt-4">
          <Button onClick={createBatch} disabled={busy}>
            Create Batch
          </Button>
        </div>
      </Card>

      {/* File Upload */}
      {batch && (
        <Card>
          <CardTitle>Upload File</CardTitle>
          <p className="text-sm text-muted mt-1">
            Batch #{batch.id} ({batch.import_type}) - Upload a .csv, .json, or .xlsx file.
          </p>
          <div className="flex flex-col gap-4 mt-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-700">File</label>
              <input
                type="file"
                accept=".csv,.json,.xlsx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="h-11 px-3 py-2 rounded-xl border border-border bg-white text-sm
                  file:mr-3 file:px-3 file:py-1 file:rounded-lg file:border-0
                  file:bg-primary/10 file:text-primary file:text-sm file:font-medium
                  file:cursor-pointer"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={uploadFile} disabled={busy || !file}>
                Upload
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Batch Status */}
      {batch && (
        <Card>
          <div className="flex items-center justify-between">
            <CardTitle>Batch Status</CardTitle>
            <Button variant="secondary" size="sm" onClick={refreshStatus} disabled={busy}>
              Refresh
            </Button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">ID</p>
              <p className="text-sm font-semibold mt-1">{batch.id}</p>
            </div>
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Status</p>
              <div className="mt-1">
                <Badge variant={statusVariant(batch.status)}>{batch.status}</Badge>
              </div>
            </div>
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Staged Rows</p>
              <p className="text-sm font-semibold mt-1">{batch.staged_rows ?? '-'}</p>
            </div>
            <div>
              <p className="text-xs text-muted font-medium uppercase tracking-wider">Posted Rows</p>
              <p className="text-sm font-semibold mt-1">{batch.posted_rows ?? '-'}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
