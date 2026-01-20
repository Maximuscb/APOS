// Overview: React component for auth interface UI.

// frontend/src/components/AuthInterface.tsx
import { useEffect, useState } from "react";
import { apiPost, clearAuthToken, getAuthToken, setAuthToken } from "../lib/api";

type User = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
};

export function AuthInterface({
  onAuthChange,
  storeId = 1,
}: {
  onAuthChange?: () => void;
  storeId?: number;
}) {
  // Note: Registration is now admin-only via the Users page or CLI
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => getAuthToken());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadSession() {
      if (!token || currentUser) return;
      try {
        const result = await apiPost<{ user: User }>("/api/auth/validate", {});
        if (active) {
          setCurrentUser(result.user);
        }
      } catch {
        // Ignore; App-level session check handles clearing tokens.
      }
    }
    loadSession();
    return () => {
      active = false;
    };
  }, [token, currentUser]);

  // Note: Registration is now admin-only - users are created via the Users page or CLI

  async function handleLogin() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ user: User; token: string }>("/api/auth/login", {
        username,
        password,
      });
      setCurrentUser(result.user);
      setToken(result.token);
      setAuthToken(result.token);
      setPassword("");
      onAuthChange?.();
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  }

  // Note: Role initialization is now CLI-only - use `flask init-roles` or `flask init-system`

  async function handleLogout() {
    setLoading(true);
    setError(null);
    try {
      await apiPost("/api/auth/logout", {});
    } catch (e: any) {
      setError(e?.message ?? "Logout failed");
    } finally {
      setLoading(false);
      setCurrentUser(null);
      setToken(null);
      clearAuthToken();
      onAuthChange?.();
    }
  }

  if (currentUser) {
    return (
      <div className="pos-card">
        <h3>User session</h3>
        <div className="pos-card__meta">
          <div>{currentUser.username}</div>
          <div className="muted">
            {currentUser.email} | ID: {currentUser.id}
          </div>
          <div className="muted">Token: {token ? "stored" : "missing"}</div>
        </div>
        <button className="btn btn--ghost" onClick={handleLogout} disabled={loading}>
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="pos-card">
      <h3>Sign In</h3>

      {error && <div className="alert">{error}</div>}

      <div className="pos-form">
        <input
          className="input"
          type="text"
          placeholder="Username or email"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
        />
        <button
          className="btn btn--primary"
          onClick={handleLogin}
          disabled={loading}
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </div>

      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        Need an account? Contact an administrator.
      </p>
    </div>
  );
}
