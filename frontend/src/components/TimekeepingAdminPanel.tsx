// Overview: Timekeeping admin panel.

import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

type TimeEntry = {
  id: number;
  user_id: number;
  store_id: number;
  clock_in_at: string;
  clock_out_at: string | null;
  status: string;
};

export function TimekeepingAdminPanel({ storeId }: { storeId: number }) {
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const result = await apiGet<{ entries: TimeEntry[] }>(`/api/timekeeping/entries?store_id=${storeId}`);
      setEntries(result.entries ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load time entries.");
    }
  }

  useEffect(() => {
    load();
  }, [storeId]);

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Timekeeping Entries</h2>
          <p className="muted">Review clock-in/out activity.</p>
        </div>
        <button className="btn btn--ghost" onClick={load}>Refresh</button>
      </div>

      <div className="table">
        <div className="table__head">
          <span>Entry</span>
          <span>User</span>
          <span>Status</span>
          <span>Clock In</span>
          <span>Clock Out</span>
        </div>
        {entries.length === 0 ? (
          <div className="table__empty muted">No entries.</div>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="table__row">
              <span>{entry.id}</span>
              <span>{entry.user_id}</span>
              <span>{entry.status}</span>
              <span>{new Date(entry.clock_in_at).toLocaleString()}</span>
              <span>{entry.clock_out_at ? new Date(entry.clock_out_at).toLocaleString() : ""}</span>
            </div>
          ))
        )}
      </div>

      {error && <div className="alert">{error}</div>}
    </div>
  );
}
