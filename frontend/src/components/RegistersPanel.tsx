import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

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
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash_cents: number;
  closing_cash_cents: number | null;
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

  const [createForm, setCreateForm] = useState({
    register_number: "",
    name: "",
    location: "",
    device_id: "",
  });

  const [openShift, setOpenShift] = useState({
    register_id: "",
    opening_cash_cents: 0,
  });

  const [closeShift, setCloseShift] = useState({
    session_id: "",
    closing_cash_cents: 0,
    notes: "",
  });

  const [noSale, setNoSale] = useState({
    session_id: "",
    approved_by_user_id: "",
    reason: "",
  });

  const [cashDrop, setCashDrop] = useState({
    session_id: "",
    amount_cents: 0,
    approved_by_user_id: "",
    reason: "",
  });

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
      const result = await apiGet<{ sessions: RegisterSession[] }>(`/api/registers/${id}/sessions?limit=10`);
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
      const result = await apiGet<{ events: DrawerEvent[] }>(`/api/registers/${id}/events?limit=20`);
      setEvents(result.events ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load drawer events");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateRegister() {
    if (!isAuthed) {
      setError("Login required to create a register.");
      return;
    }
    if (!storeId) {
      setError("Store ID required to create a register.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/registers/", {
        store_id: storeId,
        register_number: createForm.register_number,
        name: createForm.name,
        location: createForm.location || null,
        device_id: createForm.device_id || null,
      });
      setCreateForm({ register_number: "", name: "", location: "", device_id: "" });
      await loadRegisters();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create register");
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenShift() {
    if (!openShift.register_id) return;
    if (!isAuthed) {
      setError("Login required to open a shift.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/registers/${openShift.register_id}/shifts/open`, {
        opening_cash_cents: Number(openShift.opening_cash_cents),
      });
      setOpenShift({ register_id: "", opening_cash_cents: 0 });
      if (selectedRegisterId) {
        await loadRegisterDetail(Number(selectedRegisterId));
        await loadSessions(Number(selectedRegisterId));
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to open shift");
    } finally {
      setLoading(false);
    }
  }

  async function handleCloseShift() {
    if (!closeShift.session_id) return;
    if (!isAuthed) {
      setError("Login required to close a shift.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/registers/sessions/${closeShift.session_id}/close`, {
        closing_cash_cents: Number(closeShift.closing_cash_cents),
        notes: closeShift.notes || null,
      });
      setCloseShift({ session_id: "", closing_cash_cents: 0, notes: "" });
      if (selectedRegisterId) {
        await loadRegisterDetail(Number(selectedRegisterId));
        await loadSessions(Number(selectedRegisterId));
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to close shift");
    } finally {
      setLoading(false);
    }
  }

  async function handleNoSale() {
    if (!noSale.session_id) return;
    if (!isAuthed) {
      setError("Login required to log drawer events.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/registers/sessions/${noSale.session_id}/drawer/no-sale`, {
        approved_by_user_id: Number(noSale.approved_by_user_id),
        reason: noSale.reason,
      });
      setNoSale({ session_id: "", approved_by_user_id: "", reason: "" });
    } catch (e: any) {
      setError(e?.message ?? "Failed to log no-sale drawer open");
    } finally {
      setLoading(false);
    }
  }

  async function handleCashDrop() {
    if (!cashDrop.session_id) return;
    if (!isAuthed) {
      setError("Login required to log drawer events.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/registers/sessions/${cashDrop.session_id}/drawer/cash-drop`, {
        amount_cents: Number(cashDrop.amount_cents),
        approved_by_user_id: Number(cashDrop.approved_by_user_id),
        reason: cashDrop.reason,
      });
      setCashDrop({ session_id: "", amount_cents: 0, approved_by_user_id: "", reason: "" });
    } catch (e: any) {
      setError(e?.message ?? "Failed to log cash drop");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRegisters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, authVersion, isAuthed]);

  return (
    <div className="panel panel--full">
      <div className="panel__header">
        <div>
          <h2>Register Operations</h2>
          <p className="muted">Manage registers, open/close shifts, and track drawer events.</p>
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

      {!isAuthed && <div className="alert">Login required to manage registers.</div>}
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
                  <span className="chip">{registerDetail.is_active ? "Active" : "Inactive"}</span>
                  <span className="chip">
                    Session: {registerDetail.current_session?.status ?? "None"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="panel__section">
          <h3>Create Register</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Register number"
              value={createForm.register_number}
              onChange={(e) => setCreateForm({ ...createForm, register_number: e.target.value })}
            />
            <input
              className="input"
              placeholder="Name"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
            />
            <input
              className="input"
              placeholder="Location"
              value={createForm.location}
              onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })}
            />
            <input
              className="input"
              placeholder="Device ID"
              value={createForm.device_id}
              onChange={(e) => setCreateForm({ ...createForm, device_id: e.target.value })}
            />
            <button className="btn btn--primary" type="button" onClick={handleCreateRegister} disabled={loading}>
              Create register
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Shift Controls</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Register ID"
              value={openShift.register_id}
              onChange={(e) => setOpenShift({ ...openShift, register_id: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Opening cash (cents)"
              value={openShift.opening_cash_cents}
              onChange={(e) => setOpenShift({ ...openShift, opening_cash_cents: Number(e.target.value) })}
            />
            <button className="btn btn--ghost" type="button" onClick={handleOpenShift} disabled={loading}>
              Open shift
            </button>

            <input
              className="input"
              placeholder="Session ID"
              value={closeShift.session_id}
              onChange={(e) => setCloseShift({ ...closeShift, session_id: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Closing cash (cents)"
              value={closeShift.closing_cash_cents}
              onChange={(e) => setCloseShift({ ...closeShift, closing_cash_cents: Number(e.target.value) })}
            />
            <input
              className="input"
              placeholder="Notes"
              value={closeShift.notes}
              onChange={(e) => setCloseShift({ ...closeShift, notes: e.target.value })}
            />
            <button className="btn btn--ghost" type="button" onClick={handleCloseShift} disabled={loading}>
              Close shift
            </button>
          </div>
        </div>

        <div className="panel__section">
          <h3>Drawer Events</h3>
          <div className="form-grid">
            <input
              className="input"
              placeholder="Session ID"
              value={noSale.session_id}
              onChange={(e) => setNoSale({ ...noSale, session_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Approved by user ID"
              value={noSale.approved_by_user_id}
              onChange={(e) => setNoSale({ ...noSale, approved_by_user_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Reason"
              value={noSale.reason}
              onChange={(e) => setNoSale({ ...noSale, reason: e.target.value })}
            />
            <button className="btn btn--ghost" type="button" onClick={handleNoSale} disabled={loading}>
              Log no-sale open
            </button>

            <input
              className="input"
              placeholder="Session ID"
              value={cashDrop.session_id}
              onChange={(e) => setCashDrop({ ...cashDrop, session_id: e.target.value })}
            />
            <input
              className="input"
              type="number"
              placeholder="Amount (cents)"
              value={cashDrop.amount_cents}
              onChange={(e) => setCashDrop({ ...cashDrop, amount_cents: Number(e.target.value) })}
            />
            <input
              className="input"
              placeholder="Approved by user ID"
              value={cashDrop.approved_by_user_id}
              onChange={(e) => setCashDrop({ ...cashDrop, approved_by_user_id: e.target.value })}
            />
            <input
              className="input"
              placeholder="Reason"
              value={cashDrop.reason}
              onChange={(e) => setCashDrop({ ...cashDrop, reason: e.target.value })}
            />
            <button className="btn btn--ghost" type="button" onClick={handleCashDrop} disabled={loading}>
              Log cash drop
            </button>
          </div>
        </div>
      </div>

      {(sessions.length > 0 || events.length > 0) && (
        <div className="panel__grid">
          {sessions.length > 0 && (
            <div className="panel__section">
              <h3>Recent Sessions</h3>
              <div className="data-block">
                {sessions.map((session) => (
                  <div key={session.id} className="data-row">
                    <span>Session #{session.id}</span>
                    <span className="muted">
                      {session.status} | Opened {session.opened_at}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {events.length > 0 && (
            <div className="panel__section">
              <h3>Drawer Events</h3>
              <div className="data-block">
                {events.map((event) => (
                  <div key={event.id} className="data-row">
                    <span>{event.event_type}</span>
                    <span className="muted">
                    {event.amount_cents ? `$${(event.amount_cents / 100).toFixed(2)}` : "n/a"} -{" "}
                    {event.occurred_at}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
