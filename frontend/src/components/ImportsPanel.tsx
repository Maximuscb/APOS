// Overview: Import staging UI.

import { useState } from "react";
import { apiGet, apiPost, getAuthToken } from "../lib/api";

type ImportBatch = {
  id: number;
  status: string;
  import_type: string;
  staged_rows?: number;
  posted_rows?: number;
};

export function ImportsPanel() {
  const [importType, setImportType] = useState("SALES");
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function createBatch() {
    setError(null);
    try {
      const result = await apiPost<{ batch: ImportBatch }>("/api/imports/batches", {
        import_type: importType,
      });
      setBatch(result.batch);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create batch.");
    }
  }

  async function uploadFile(file: File) {
    if (!batch) return;
    setError(null);
    const form = new FormData();
    form.append("file", file);

    const token = getAuthToken();
    const res = await fetch(`/api/imports/batches/${batch.id}/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data?.error ?? "Upload failed.");
      return;
    }
  }

  async function refreshStatus() {
    if (!batch) return;
    try {
      const result = await apiGet<{ batch: ImportBatch }>(`/api/imports/batches/${batch.id}/status`);
      setBatch(result.batch);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load status.");
    }
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Imports</h2>
          <p className="muted">Stage CSV/JSON/Excel files for mapping and posting.</p>
        </div>
      </div>

      <div className="panel__grid">
        <div className="panel__section">
          <label className="field">
            <span>Import type</span>
            <select className="input" value={importType} onChange={(e) => setImportType(e.target.value)}>
              <option value="PRODUCTS">Products</option>
              <option value="SALES">Sales</option>
              <option value="INVENTORY">Inventory</option>
            </select>
          </label>
          <button className="btn btn--primary" type="button" onClick={createBatch}>
            Create batch
          </button>
        </div>
        <div className="panel__section">
          <label className="field">
            <span>Upload file</span>
            <input
              className="input"
              type="file"
              accept=".csv,.json,.xlsx"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  uploadFile(e.target.files[0]);
                }
              }}
              disabled={!batch}
            />
          </label>
          <button className="btn btn--ghost" type="button" onClick={refreshStatus} disabled={!batch}>
            Refresh status
          </button>
          {batch && (
            <div className="muted">
              Batch #{batch.id} - {batch.status} (staged: {batch.staged_rows ?? 0}, posted: {batch.posted_rows ?? 0})
            </div>
          )}
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
    </div>
  );
}
