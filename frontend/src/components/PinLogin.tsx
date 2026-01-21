// Overview: PIN-first login for Register Mode.

import { useState } from "react";
import { apiPost } from "../lib/api";

type PinLoginProps = {
  onSuccess: (token: string) => void;
  onFallback: () => void;
};

export function PinLogin({ onSuccess, onFallback }: PinLoginProps) {
  const [pin, setPin] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handlePinLogin() {
    setError(null);
    if (!pin || pin.length !== 6 || !/^[0-9]+$/.test(pin)) {
      setError("Enter a 6-digit PIN.");
      return;
    }

    setLoading(true);
    try {
      const result = await apiPost<{ token: string }>("/api/auth/login-pin", { pin });
      onSuccess(result.token);
    } catch (e: any) {
      setError(e?.message ?? "PIN login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handlePasswordLogin() {
    setError(null);
    if (!identifier || !password) {
      setError("Enter username/email and password.");
      return;
    }
    setLoading(true);
    try {
      const result = await apiPost<{ token: string }>("/api/auth/login", {
        identifier,
        password,
      });
      onSuccess(result.token);
    } catch (e: any) {
      setError(e?.message ?? "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="register-login">
      <div className="register-login__card">
        <div className="register-login__title">Register Mode</div>
        <p className="muted">Enter your PIN to start a shift.</p>

        {!showPassword && (
          <>
            <input
              className="input"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="6-digit PIN"
              inputMode="numeric"
              maxLength={6}
            />
            <button className="btn btn--primary" type="button" onClick={handlePinLogin} disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => setShowPassword(true)}>
              Use password
            </button>
          </>
        )}

        {showPassword && (
          <>
            <input
              className="input"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Username or email"
            />
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
            />
            <button className="btn btn--primary" type="button" onClick={handlePasswordLogin} disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => setShowPassword(false)}>
              Use PIN
            </button>
          </>
        )}

        <button className="btn btn--ghost" type="button" onClick={onFallback}>
          Back to Operations Suite
        </button>

        {error && <div className="alert">{error}</div>}
      </div>
    </div>
  );
}
