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

  const tableStyle: React.CSSProperties = {
    width: "100%",
    borderCollapse: "collapse",
    border: "1px solid #ddd",
    marginTop: 10,
  };

  const thStyle: React.CSSProperties = {
    textAlign: "left",
    fontSize: 12,
    padding: "8px 10px",
    borderBottom: "1px solid #ddd",
    background: "#f6f6f6",
    whiteSpace: "nowrap",
  };

  const tdStyle: React.CSSProperties = {
    fontSize: 12,
    padding: "8px 10px",
    borderBottom: "1px solid #eee",
    verticalAlign: "top",
  };

  return (
    <div style={{ marginTop: 12, padding: 12, border: "1px solid #ddd" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Master Ledger (read-only)</h3>
        <button
          onClick={() => load(false)}
          disabled={loading}
          style={{ padding: "6px 10px", cursor: "pointer" }}
          title="Reload master ledger"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error ? <div style={{ marginTop: 8, color: "#b00020", fontSize: 12 }}>{error}</div> : null}

      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Occurred (Local)</th>
            <th style={thStyle}>Category</th>
            <th style={thStyle}>Event</th>
            <th style={thStyle}>Entity</th>
            <th style={thStyle}>Entity ID</th>
            <th style={thStyle}>Note</th>
            <th style={thStyle}>Event ID</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
                <td style={tdStyle} colSpan={7}>
                  {loading ? "Loading..." : "No ledger events found."}
                </td>
              </tr>
            ) : (
            rows.map((r) => (
              <tr key={r.id}>
                <td style={tdStyle}>{r.occurred_at ? utcIsoToLocalDisplay(r.occurred_at) : ""}</td>
                <td style={tdStyle}>{r.event_category}</td>
                <td style={tdStyle}>{r.event_type}</td>
                <td style={tdStyle}>{r.entity_type}</td>
                <td style={tdStyle}>{r.entity_id}</td>
                <td style={tdStyle}>{r.note ?? ""}</td>
                <td style={tdStyle}>{r.id}</td>
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
            style={{ padding: "6px 10px", cursor: "pointer" }}
          >
            {loading ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
