// frontend/src/components/AuthInterface.tsx
import { useState } from "react";
import { apiPost } from "../lib/api";

type User = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
};

export function AuthInterface({ onAuthChange }: { onAuthChange?: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("apos_token"));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRegister() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiPost<{ user: User }>("/api/auth/register", {
        username,
        email,
        password,
        store_id: 1,
      });
      alert("User registered successfully!");
      setMode("login");
      setPassword("");
    } catch (e: any) {
      setError(e?.message ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  }

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
      localStorage.setItem("apos_token", result.token);
      setPassword("");
      onAuthChange?.();
    } catch (e: any) {
      setError(e?.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function initRoles() {
    try {
      await apiPost("/api/auth/roles/init", {});
      alert("Default roles initialized!");
    } catch (e: any) {
      setError(e?.message ?? "Failed to init roles");
    }
  }

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
      localStorage.removeItem("apos_token");
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
      <h3>Authentication</h3>

      {error && <div className="alert">{error}</div>}

      <div className="pos-tabs">
        <button
          onClick={() => setMode("login")}
          className={`pos-tab ${mode === "login" ? "pos-tab--active" : ""}`}
        >
          Login
        </button>
        <button
          onClick={() => setMode("register")}
          className={`pos-tab ${mode === "register" ? "pos-tab--active" : ""}`}
        >
          Register
        </button>
        <button className="btn btn--ghost pos-tabs__action" onClick={initRoles}>
          Init roles
        </button>
      </div>

      <div className="pos-form">
        <input
          className="input"
          type="text"
          placeholder="Username or email"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        {mode === "register" && (
          <input
            className="input"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        )}
        <input
          className="input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (mode === "login" ? handleLogin() : handleRegister())}
        />
        <button
          className="btn btn--primary"
          onClick={mode === "login" ? handleLogin : handleRegister}
          disabled={loading}
        >
          {loading ? "Working..." : mode === "login" ? "Login" : "Register"}
        </button>
      </div>
    </div>
  );
}
