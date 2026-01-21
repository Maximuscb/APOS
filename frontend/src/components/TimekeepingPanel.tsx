// Overview: Timekeeping controls for Register Mode.

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

type TimekeepingPanelProps = {
  storeId: number;
};

type StatusResponse = {
  status: string;
  on_break: boolean;
  entry: { id: number } | null;
};

export function TimekeepingPanel({ storeId }: TimekeepingPanelProps) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus() {
    try {
      const result = await apiGet<StatusResponse>("/api/timekeeping/status");
      setStatus(result);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load status.");
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function clockIn() {
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/timekeeping/clock-in", { store_id: storeId });
      await loadStatus();
    } catch (e: any) {
      setError(e?.message ?? "Clock in failed.");
    } finally {
      setLoading(false);
    }
  }

  async function clockOut() {
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/timekeeping/clock-out", {});
      await loadStatus();
    } catch (e: any) {
      setError(e?.message ?? "Clock out failed.");
    } finally {
      setLoading(false);
    }
  }

  async function startBreak() {
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/timekeeping/break/start", {});
      await loadStatus();
    } catch (e: any) {
      setError(e?.message ?? "Break start failed.");
    } finally {
      setLoading(false);
    }
  }

  async function endBreak() {
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/timekeeping/break/end", {});
      await loadStatus();
    } catch (e: any) {
      setError(e?.message ?? "Break end failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="panel__header">
        <div>
          <h2>Timekeeping</h2>
          <p className="muted">Clock in/out and manage breaks.</p>
        </div>
        <button className="btn btn--ghost" type="button" onClick={loadStatus}>
          Refresh status
        </button>
      </div>

      <div className="panel__grid">
        <div className="panel__section">
          <div className="chip">Status: {status?.status ?? "Unknown"}</div>
        </div>
        <div className="panel__section">
          <button className="btn btn--primary" type="button" onClick={clockIn} disabled={loading}>
            Clock in
          </button>
          <button className="btn btn--ghost" type="button" onClick={clockOut} disabled={loading}>
            Clock out
          </button>
        </div>
        <div className="panel__section">
          <button className="btn btn--primary" type="button" onClick={startBreak} disabled={loading}>
            Start break
          </button>
          <button className="btn btn--ghost" type="button" onClick={endBreak} disabled={loading}>
            End break
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
    </div>
  );
}
