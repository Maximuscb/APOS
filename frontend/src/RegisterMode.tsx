// Overview: Fullscreen Register Mode workflow.

import { useEffect, useState } from "react";
import "./App.css";
import { apiGet, apiPost, clearAuthToken, getAuthToken, setAuthToken } from "./lib/api";
import { SalesInterface } from "./components/SalesInterface";
import { PaymentsPanel } from "./components/PaymentsPanel";
import { PinLogin } from "./components/PinLogin";
import { TimekeepingPanel } from "./components/TimekeepingPanel";
import { ShiftPanel } from "./components/ShiftPanel";

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  store_id: number;
};

type User = {
  id: number;
  username: string;
  email: string;
  store_id: number | null;
};

export function RegisterMode({ onExit }: { onExit: () => void }) {
  const [authStatus, setAuthStatus] = useState<"unknown" | "authenticated" | "guest">("unknown");
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [storeId, setStoreId] = useState(1);
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [activeTab, setActiveTab] = useState<"sales" | "payments" | "shift" | "time">("sales");

  async function loadSession() {
    const token = getAuthToken();
    if (!token) {
      setAuthStatus("guest");
      setUser(null);
      setPermissions([]);
      return;
    }
    try {
      const result = await apiPost<{ user: User; permissions?: string[] }>("/api/auth/validate", {});
      setUser(result.user);
      setPermissions(result.permissions ?? []);
      setAuthStatus("authenticated");
      if (result.user?.store_id && result.user.store_id !== storeId) {
        setStoreId(result.user.store_id);
      }
    } catch {
      clearAuthToken();
      setAuthStatus("guest");
      setUser(null);
      setPermissions([]);
    }
  }

  async function loadProducts() {
    setLoadingProducts(true);
    try {
      const result = await apiGet<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
      setProducts(result.items ?? []);
    } finally {
      setLoadingProducts(false);
    }
  }

  useEffect(() => {
    loadSession();
  }, []);

  useEffect(() => {
    if (authStatus === "authenticated") {
      loadProducts();
    }
  }, [authStatus, storeId]);

  if (authStatus !== "authenticated") {
    return (
      <div className="register-shell">
        <PinLogin
          onSuccess={(token) => {
            setAuthToken(token);
            loadSession();
          }}
          onFallback={() => onExit()}
        />
      </div>
    );
  }

  return (
    <div className="register-shell">
      <header className="register-header">
        <div>
          <div className="register-eyebrow">Register Mode</div>
          <h1>Store {storeId}</h1>
          <div className="register-meta">Signed in: {user?.username}</div>
        </div>
        <div className="register-actions">
          <button className="btn btn--ghost" type="button" onClick={() => clearAuthToken()}>
            Sign out
          </button>
          <button className="btn btn--primary" type="button" onClick={onExit}>
            Exit
          </button>
        </div>
      </header>

      <nav className="register-tabs">
        <button
          className={`register-tab ${activeTab === "sales" ? "register-tab--active" : ""}`}
          onClick={() => setActiveTab("sales")}
        >
          Sales
        </button>
        <button
          className={`register-tab ${activeTab === "payments" ? "register-tab--active" : ""}`}
          onClick={() => setActiveTab("payments")}
        >
          Payments
        </button>
        <button
          className={`register-tab ${activeTab === "shift" ? "register-tab--active" : ""}`}
          onClick={() => setActiveTab("shift")}
        >
          Shift
        </button>
        <button
          className={`register-tab ${activeTab === "time" ? "register-tab--active" : ""}`}
          onClick={() => setActiveTab("time")}
        >
          Timekeeping
        </button>
      </nav>

      <main className="register-content">
        {activeTab === "sales" && (
          <div className="panel panel--full">
            {loadingProducts ? (
              <div className="panel__placeholder">Loading catalog...</div>
            ) : (
              <SalesInterface products={products} storeId={storeId} isAuthed={authStatus === "authenticated"} />
            )}
          </div>
        )}

        {activeTab === "payments" && (
          <div className="panel panel--full">
            <PaymentsPanel authVersion={0} isAuthed={authStatus === "authenticated"} />
          </div>
        )}

        {activeTab === "shift" && (
          <div className="panel panel--full">
            <ShiftPanel storeId={storeId} permissions={permissions} />
          </div>
        )}

        {activeTab === "time" && (
          <div className="panel panel--full">
            <TimekeepingPanel storeId={storeId} />
          </div>
        )}
      </main>
    </div>
  );
}
