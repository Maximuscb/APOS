// frontend/src/components/AuthInterface.tsx
import { useState } from "react";
import { apiPost } from "../lib/api";

type User = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
};

export function AuthInterface() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
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
      const result = await apiPost<{ user: User }>("/api/auth/login", {
        username,
        password,
      });
      setCurrentUser(result.user);
      setPassword("");
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

  if (currentUser) {
    return (
      <div style={{ marginTop: 20, padding: 12, border: "1px solid #ddd" }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
          User: {currentUser.username}
        </h3>
        <div style={{ fontSize: 13, color: "#666" }}>
          Email: {currentUser.email} | ID: {currentUser.id}
        </div>
        <button
          onClick={() => setCurrentUser(null)}
          style={{ marginTop: 8, padding: "6px 12px" }}
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 20, padding: 12, border: "1px solid #ddd" }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
        Authentication (Stub)
      </h3>

      {error && (
        <div style={{ padding: 8, background: "#fff5f5", color: "#9b1c1c", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={() => setMode("login")}
          style={{
            padding: "6px 12px",
            background: mode === "login" ? "#3b82f6" : "#e5e7eb",
            color: mode === "login" ? "white" : "black",
            border: "none",
          }}
        >
          Login
        </button>
        <button
          onClick={() => setMode("register")}
          style={{
            padding: "6px 12px",
            background: mode === "register" ? "#3b82f6" : "#e5e7eb",
            color: mode === "register" ? "white" : "black",
            border: "none",
          }}
        >
          Register
        </button>
        <button onClick={initRoles} style={{ padding: "6px 12px", marginLeft: "auto" }}>
          Init Roles
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          style={{ padding: 8 }}
        />
        {mode === "register" && (
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ padding: 8 }}
          />
        )}
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (mode === "login" ? handleLogin() : handleRegister())}
          style={{ padding: 8 }}
        />
        <button
          onClick={mode === "login" ? handleLogin : handleRegister}
          disabled={loading}
          style={{ padding: "8px 16px" }}
        >
          {loading ? "..." : mode === "login" ? "Login" : "Register"}
        </button>
      </div>

      <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
        Note: Stub implementation (STUB_HASH_password)
      </div>
    </div>
  );
}
