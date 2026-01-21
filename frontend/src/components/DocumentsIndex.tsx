// Overview: Unified documents index UI.

import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

type DocumentRow = {
  id: number;
  type: string;
  document_number: string | null;
  store_id: number | null;
  status: string | null;
  occurred_at: string | null;
  user_id: number | null;
  register_id: number | null;
};

export function DocumentsIndex({ storeId }: { storeId: number }) {
  const [items, setItems] = useState<DocumentRow[]>([]);
  const [docType, setDocType] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    const params = new URLSearchParams();
    params.set("store_id", String(storeId));
    if (docType) params.set("type", docType);
    if (fromDate) params.set("from_date", new Date(fromDate).toISOString());
    if (toDate) params.set("to_date", new Date(toDate).toISOString());

    try {
      const result = await apiGet<{ items: DocumentRow[] }>(`/api/documents?${params.toString()}`);
      setItems(result.items ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load documents.");
    }
  }

  useEffect(() => {
    load();
  }, [storeId]);

  return (
    <div className="panel panel--full">
      <div className="panel__header panel__header--split">
        <div>
          <h2>Documents Index</h2>
          <p className="muted">Filter and open posted documents.</p>
        </div>
        <div className="panel__actions">
          <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="">All types</option>
            <option value="SALES">Sales</option>
            <option value="RECEIVES">Receives</option>
            <option value="ADJUSTMENTS">Adjustments</option>
            <option value="COUNTS">Counts</option>
            <option value="TRANSFERS">Transfers</option>
            <option value="RETURNS">Returns</option>
            <option value="PAYMENTS">Payments</option>
            <option value="SHIFTS">Shifts</option>
            <option value="IMPORTS">Imports</option>
          </select>
          <input
            className="input"
            type="datetime-local"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
          <input
            className="input"
            type="datetime-local"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
          <button className="btn btn--ghost" type="button" onClick={load}>
            Apply
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <div className="table">
        <div className="table__head">
          <span>Type</span>
          <span>Doc #</span>
          <span>Status</span>
          <span>Occurred</span>
          <span>User</span>
        </div>
        {items.length === 0 ? (
          <div className="table__empty muted">No documents found.</div>
        ) : (
          items.map((doc) => (
            <div key={`${doc.type}-${doc.id}`} className="table__row">
              <span>{doc.type}</span>
              <span>{doc.document_number ?? `#${doc.id}`}</span>
              <span>{doc.status ?? ""}</span>
              <span>{doc.occurred_at ? new Date(doc.occurred_at).toLocaleString() : ""}</span>
              <span>{doc.user_id ?? ""}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
