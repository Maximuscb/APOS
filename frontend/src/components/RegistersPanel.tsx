// Overview: Read-only register status and history view for Operations suite.

import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

type Register = {
  id: number;
  store_id: number;
  register_number: string;
  name: string;
  location: string | null;
  device_id: string | null;
  is_active: boolean;
};

type RegisterSession = {
  id: number;
  register_id: number;
  user_id: number;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash_cents: number;
  closing_cash_cents: number | null;
  variance_cents: number | null;
};

type DrawerEvent = {
  id: number;
  register_id: number;
  register_session_id: number;
  event_type: string;
  amount_cents: number | null;
  reason: string | null;
  occurred_at: string;
};

export function RegistersPanel({
  authVersion,
  storeId,
  onStoreIdChange,
  isAuthed,
}: {
  authVersion: number;
  storeId: number;
  onStoreIdChange: (next: number) => void;
  isAuthed: boolean;
}) {
  const [registers, setRegisters] = useState<Register[]>([]);
  const [selectedRegisterId, setSelectedRegisterId] = useState<number | "">("");
  const [registerDetail, setRegisterDetail] = useState<Register & { current_session: RegisterSession | null } | null>(
    null
  );
  const [sessions, setSessions] = useState<RegisterSession[]>([]);
  const [events, setEvents] = useState<DrawerEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadRegisters() {
    if (!isAuthed) {
      setRegisters([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const query = storeId ? `?store_id=${storeId}` : "";
      const result = await apiGet<{ registers: Register[] }>(`/api/registers${query}`);
      setRegisters(result.registers ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load registers");
    } finally {
      setLoading(false);
    }
  }

  async function loadRegisterDetail(id: number) {
    if (!isAuthed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<Register & { current_session: RegisterSession | null }>(`/api/registers/${id}`);
      setRegisterDetail(result);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load register");
    } finally {
      setLoading(false);
    }
  }

  async function loadSessions(id: number) {
    if (!isAuthed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ sessions: RegisterSession[] }>(`/api/registers/${id}/sessions?limit=20`);
      setSessions(result.sessions ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }

  async function loadEvents(id: number) {
    if (!isAuthed) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<{ events: DrawerEvent[] }>(`/api/registers/${id}/events?limit=50`);
      setEvents(result.events ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load drawer events");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRegisters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, authVersion, isAuthed]);

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "--";
    const d = new Date(dateStr);
    return d.toLocaleString();
  }

  function formatCents(cents: number | null | undefined): string {
    if (cents == null) return "--";
    return `$${(cents / 100).toFixed(2)}`;
  }

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Register Status</h2>
          <p className="muted">View register status, session history, and drawer events. Shift operations are performed in Register Mode.</p>
        </div>
        <div className="panel__actions">
          <div className="field">
            <label>Store ID</label>
            <input
              className="input"
              type="number"
              min="1"
              value={storeId}
              onChange={(e) => onStoreIdChange(Number(e.target.value))}
            />
          </div>
          <button className="btn btn--ghost" type="button" onClick={loadRegisters} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {!isAuthed && <div className="alert">Login required to view registers.</div>}
      {error && <div className="alert">{error}</div>}

      <div className="panel__grid">
        <div className="panel__section">
          <h3>Registers</h3>
          <div className="form-grid">
            <select
              className="input"
              value={selectedRegisterId}
              onChange={(e) => {
                const value = e.target.value ? Number(e.target.value) : "";
                setSelectedRegisterId(value);
                if (value) {
                  loadRegisterDetail(value);
                  loadSessions(value);
                  loadEvents(value);
                } else {
                  setRegisterDetail(null);
                  setSessions([]);
                  setEvents([]);
                }
              }}
            >
              <option value="">Select register</option>
              {registers.map((register) => (
                <option key={register.id} value={register.id}>
                  {register.register_number} - {register.name}
                </option>
              ))}
            </select>
            {registerDetail && (
              <div className="data-block">
                <div>
                  <strong>{registerDetail.name}</strong>
                </div>
                <div className="muted">
                  {registerDetail.location ?? "No location"} | {registerDetail.device_id ?? "No device ID"}
                </div>
                <div className="chip-row">
                  <span className={`chip ${registerDetail.is_active ? "chip--success" : "chip--warn"}`}>
                    {registerDetail.is_active ? "Active" : "Inactive"}
                  </span>
                  <span className={`chip ${registerDetail.current_session?.status === "OPEN" ? "chip--success" : ""}`}>
                    Session: {registerDetail.current_session?.status ?? "None"}
                  </span>
                </div>
                {registerDetail.current_session && (
                  <div className="muted" style={{ marginTop: "8px" }}>
                    Session #{registerDetail.current_session.id} |
                    Opened: {formatDate(registerDetail.current_session.opened_at)} |
                    Opening cash: {formatCents(registerDetail.current_session.opening_cash_cents)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="panel__section">
          <h3>Register List</h3>
          <div className="data-block">
            {registers.length === 0 ? (
              <div className="muted">No registers found for this store.</div>
            ) : (
              registers.map((reg) => (
                <div key={reg.id} className="data-row">
                  <span>
                    <strong>{reg.register_number}</strong> - {reg.name}
                  </span>
                  <span className="chip-row">
                    <span className={`chip ${reg.is_active ? "chip--success" : "chip--warn"}`}>
                      {reg.is_active ? "Active" : "Inactive"}
                    </span>
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {sessions.length > 0 && (
        <div className="panel__grid">
          <div className="panel__section panel__section--wide">
            <h3>Session History</h3>
            <div className="table">
              <div className="table__head">
                <span>Session</span>
                <span>Status</span>
                <span>Opened</span>
                <span>Closed</span>
                <span>Opening</span>
                <span>Closing</span>
                <span>Variance</span>
              </div>
              {sessions.map((session) => (
                <div key={session.id} className="table__row">
                  <span>#{session.id}</span>
                  <span className={session.status === "OPEN" ? "text-success" : ""}>{session.status}</span>
                  <span>{formatDate(session.opened_at)}</span>
                  <span>{formatDate(session.closed_at)}</span>
                  <span>{formatCents(session.opening_cash_cents)}</span>
                  <span>{formatCents(session.closing_cash_cents)}</span>
                  <span className={session.variance_cents != null && session.variance_cents < 0 ? "text-error" : session.variance_cents != null && session.variance_cents > 0 ? "text-success" : ""}>
                    {formatCents(session.variance_cents)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="panel__grid">
          <div className="panel__section panel__section--wide">
            <h3>Drawer Events</h3>
            <div className="table">
              <div className="table__head">
                <span>Event</span>
                <span>Session</span>
                <span>Amount</span>
                <span>Reason</span>
                <span>Time</span>
              </div>
              {events.map((event) => (
                <div key={event.id} className="table__row">
                  <span>{event.event_type}</span>
                  <span>#{event.register_session_id}</span>
                  <span>{formatCents(event.amount_cents)}</span>
                  <span className="muted">{event.reason ?? "--"}</span>
                  <span>{formatDate(event.occurred_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
