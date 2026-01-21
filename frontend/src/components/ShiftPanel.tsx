// Overview: Register shift open/close controls for Register Mode.

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";

type Register = {
  id: number;
  register_number: string;
  name: string;
  store_id: number;
  current_session?: { id: number; status: string } | null;
};

type ShiftPanelProps = {
  storeId: number;
  permissions: string[];
};

export function ShiftPanel({ storeId }: ShiftPanelProps) {
  const [registers, setRegisters] = useState<Register[]>([]);
  const [registerId, setRegisterId] = useState<number | "">("");
  const [openingCash, setOpeningCash] = useState("0");
  const [closingCash, setClosingCash] = useState("0");
  const [sessionId, setSessionId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadRegisters() {
    setError(null);
    try {
      const result = await apiGet<{ registers: Register[] }>(`/api/registers?store_id=${storeId}`);
      setRegisters(result.registers ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load registers.");
    }
  }

  async function refreshSession(regId: number) {
    try {
      const result = await apiGet<Register>(`/api/registers/${regId}`);
      setSessionId(result.current_session?.id ?? "");
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadRegisters();
  }, [storeId]);

  async function openShift() {
    setError(null);
    if (!registerId) {
      setError("Select a register.");
      return;
    }
    const opening_cash_cents = Math.round(Number(openingCash) * 100);
    if (!Number.isFinite(opening_cash_cents) || opening_cash_cents < 0) {
      setError("Opening cash must be >= 0.");
      return;
    }

    setLoading(true);
    try {
      const result = await apiPost<{ session: { id: number } }>(
        `/api/registers/${registerId}/shifts/open`,
        { opening_cash_cents }
      );
      setSessionId(result.session.id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to open shift.");
    } finally {
      setLoading(false);
    }
  }

  async function closeShift() {
    setError(null);
    if (!sessionId) {
      setError("Select an open session.");
      return;
    }
    const closing_cash_cents = Math.round(Number(closingCash) * 100);
    if (!Number.isFinite(closing_cash_cents) || closing_cash_cents < 0) {
      setError("Closing cash must be >= 0.");
      return;
    }

    setLoading(true);
    try {
      await apiPost(`/api/registers/sessions/${sessionId}/close`, {
        closing_cash_cents,
      });
      setSessionId("");
      await refreshSession(Number(registerId));
    } catch (e: any) {
      setError(e?.message ?? "Failed to close shift.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="panel__header">
        <div>
          <h2>Shift Controls</h2>
          <p className="muted">Open and close a register shift.</p>
        </div>
        <button className="btn btn--ghost" type="button" onClick={loadRegisters}>
          Refresh registers
        </button>
      </div>

      <div className="panel__grid">
        <div className="panel__section">
          <label className="field">
            <span>Register</span>
            <select
              className="input"
              value={registerId}
              onChange={(e) => {
                const value = e.target.value ? Number(e.target.value) : "";
                setRegisterId(value);
                if (value) {
                  refreshSession(value);
                }
              }}
            >
              <option value="">Select register</option>
              {registers.map((reg) => (
                <option key={reg.id} value={reg.id}>
                  {reg.register_number} - {reg.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="panel__section">
          <label className="field">
            <span>Opening cash (USD)</span>
            <input
              className="input"
              value={openingCash}
              onChange={(e) => setOpeningCash(e.target.value)}
              inputMode="decimal"
            />
          </label>
          <button className="btn btn--primary" type="button" onClick={openShift} disabled={loading}>
            Open shift
          </button>
        </div>
        <div className="panel__section">
          <label className="field">
            <span>Open session ID</span>
            <input className="input" value={sessionId} readOnly />
          </label>
          <label className="field">
            <span>Closing cash (USD)</span>
            <input
              className="input"
              value={closingCash}
              onChange={(e) => setClosingCash(e.target.value)}
              inputMode="decimal"
            />
          </label>
          <button className="btn btn--primary" type="button" onClick={closeShift} disabled={loading}>
            Close shift
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
    </div>
  );
}
