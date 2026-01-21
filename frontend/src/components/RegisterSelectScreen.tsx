// Overview: Register selection screen shown after PIN login in Register Mode.

import { useState } from "react";
import { apiPost } from "../lib/api";

type Register = {
  id: number;
  register_number: string;
  name: string;
  location: string | null;
  current_session?: { id: number; status: string; user_id: number } | null;
};

type RegisterSelectScreenProps = {
  registers: Register[];
  userId: number;
  onSessionStarted: (registerId: number, sessionId: number, registerNumber: string) => void;
  onCancel: () => void;
};

export function RegisterSelectScreen({
  registers,
  userId,
  onSessionStarted,
  onCancel,
}: RegisterSelectScreenProps) {
  const [selectedRegisterId, setSelectedRegisterId] = useState<number | null>(null);
  const [openingCash, setOpeningCash] = useState("100.00");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRegister = registers.find((r) => r.id === selectedRegisterId);
  const hasOtherUserSession =
    selectedRegister?.current_session &&
    selectedRegister.current_session.user_id !== userId;

  async function handleOpenShift() {
    if (!selectedRegisterId) {
      setError("Please select a register.");
      return;
    }

    if (hasOtherUserSession) {
      setError("This register has an open session from another user.");
      return;
    }

    const opening_cash_cents = Math.round(Number(openingCash) * 100);
    if (!Number.isFinite(opening_cash_cents) || opening_cash_cents < 0) {
      setError("Opening cash must be a valid amount >= $0.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ session: { id: number } }>(
        `/api/registers/${selectedRegisterId}/shifts/open`,
        { opening_cash_cents }
      );
      const reg = registers.find((r) => r.id === selectedRegisterId);
      onSessionStarted(selectedRegisterId, result.session.id, reg?.register_number ?? "");
    } catch (e: any) {
      setError(e?.message ?? "Failed to open shift.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="register-select">
      <div className="register-select__card">
        <h2 className="register-select__title">Select Register</h2>
        <p className="muted">Choose a register to open your shift.</p>

        {error && <div className="alert">{error}</div>}

        <div className="register-select__list">
          {registers.length === 0 ? (
            <div className="muted">No registers available for this store.</div>
          ) : (
            registers.map((reg) => {
              const hasSession = reg.current_session?.status === "OPEN";
              const isOwnSession = hasSession && reg.current_session?.user_id === userId;
              const isOtherSession = hasSession && !isOwnSession;

              return (
                <button
                  key={reg.id}
                  type="button"
                  className={`register-select__item ${selectedRegisterId === reg.id ? "register-select__item--selected" : ""} ${isOtherSession ? "register-select__item--unavailable" : ""}`}
                  onClick={() => setSelectedRegisterId(reg.id)}
                  disabled={isOtherSession}
                >
                  <div className="register-select__item-main">
                    <strong>{reg.register_number}</strong>
                    <span className="muted">{reg.name}</span>
                  </div>
                  <div className="register-select__item-status">
                    {isOwnSession && <span className="chip chip--success">Your session</span>}
                    {isOtherSession && <span className="chip chip--warn">In use</span>}
                    {!hasSession && <span className="chip">Available</span>}
                  </div>
                </button>
              );
            })
          )}
        </div>

        <div className="register-select__form">
          <label className="field">
            <span>Opening Cash (USD)</span>
            <input
              className="input"
              type="text"
              inputMode="decimal"
              value={openingCash}
              onChange={(e) => setOpeningCash(e.target.value)}
              placeholder="100.00"
            />
          </label>
        </div>

        <div className="register-select__actions">
          <button
            className="btn btn--primary"
            type="button"
            onClick={handleOpenShift}
            disabled={loading || !selectedRegisterId}
          >
            {loading ? "Opening..." : "Open Shift"}
          </button>
          <button className="btn btn--ghost" type="button" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
