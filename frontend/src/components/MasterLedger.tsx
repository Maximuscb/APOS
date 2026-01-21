// Overview: React component for master ledger UI.

// frontend/src/components/MasterLedger.tsx
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../lib/api";
import { datetimeLocalToUtcIso, utcIsoToLocalDisplay } from "../lib/time";

type LedgerEvent = {
  id: number;
  store_id: number;
  event_type: string;
  event_category: string;
  entity_type: string;
  entity_id: number;
  actor_user_id: number | null;
  register_id: number | null;
  register_session_id: number | null;
  sale_id: number | null;
  payment_id: number | null;
  return_id: number | null;
  transfer_id: number | null;
  count_id: number | null;
  cash_drawer_event_id: number | null;
  occurred_at: string | null; // UTC ISO Z
  created_at: string | null; // UTC ISO Z
  note: string | null;
  payload: string | null;
};

type LedgerResponse = {
  items: LedgerEvent[];
  next_cursor: string | null;
  limit: number;
};

type Props = {
  storeId: number;          // keep explicit; App can hardcode 1 for now
  asOf: string;             // datetime-local string from App
  refreshToken: number;     // bump to reload
  limit?: number;           // default 100
};

export function MasterLedger({ storeId, asOf, refreshToken, limit = 100 }: Props) {
  const [rows, setRows] = useState<LedgerEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const asOfUtcIso = useMemo(() => datetimeLocalToUtcIso(asOf), [asOf]);

  async function load(isLoadMore = false) {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();
      params.set("store_id", String(storeId));
      params.set("limit", String(Math.max(1, Math.min(limit, 500))));
      if (asOfUtcIso) params.set("as_of", asOfUtcIso);
      if (isLoadMore && nextCursor) params.set("cursor", nextCursor);

      const data = await apiGet<LedgerResponse>(`/api/ledger?${params.toString()}`);
      const items = Array.isArray(data?.items) ? data.items : [];
      setRows((prev) => (isLoadMore ? [...prev, ...items] : items));
      setNextCursor(data?.next_cursor ?? null);
    } catch (e: any) {
      setError(e?.message || "Failed to load master ledger.");
      setRows([]);
      setNextCursor(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, asOfUtcIso, refreshToken]);

  return (
    <div className="form-card" style={{ marginTop: 12 }}>
      <div className="form-row" style={{ justifyContent: "space-between" }}>
        <h3 className="form-title" style={{ margin: 0 }}>Master Ledger (read-only)</h3>
        <button
          onClick={() => load(false)}
          disabled={loading}
          className="btn btn--ghost btn--sm"
          title="Reload master ledger"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error ? (
        <div className="notice notice--error" style={{ marginTop: 8 }}>
          {error}
        </div>
      ) : null}

      <table className="data-table">
        <thead>
          <tr>
            <th>Occurred (Local)</th>
            <th>Category</th>
            <th>Event</th>
            <th>Entity</th>
            <th>Entity ID</th>
            <th>Note</th>
            <th>Event ID</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={7}>
                {loading ? "Loading..." : "No ledger events found."}
              </td>
            </tr>
          ) : (
            rows.map((r) => (
              <tr key={r.id}>
                <td>{r.occurred_at ? utcIsoToLocalDisplay(r.occurred_at) : ""}</td>
                <td>{r.event_category}</td>
                <td>{r.event_type}</td>
                <td>{r.entity_type}</td>
                <td>{r.entity_id}</td>
                <td>{r.note ?? ""}</td>
                <td>{r.id}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {nextCursor && (
        <div style={{ marginTop: 10 }}>
          <button
            onClick={() => load(true)}
            disabled={loading}
            className="btn btn--ghost btn--sm"
          >
            {loading ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
