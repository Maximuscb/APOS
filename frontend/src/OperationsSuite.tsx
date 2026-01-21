// Overview: Operations Suite layout and navigation.

import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { apiDelete, apiGet, apiPost, apiPut, clearAuthToken, getAuthToken } from "./lib/api";
import { AdjustInventoryForm } from "./components/AdjustInventoryForm";
import { CreateProductForm } from "./components/CreateProductForm";
import { InventoryLedger } from "./components/InventoryLedger";
import { MasterLedger } from "./components/MasterLedger";
import { ProductsTable } from "./components/ProductsTable";
import { ReceiveInventoryForm } from "./components/ReceiveInventoryForm";
import { IdentifierLookup } from "./components/IdentifierLookup";
import { AuthInterface } from "./components/AuthInterface";
import { LifecycleManager } from "./components/LifecycleManager";
import { RegistersPanel } from "./components/RegistersPanel";
import { PaymentsPanel } from "./components/PaymentsPanel";
import { AuditPanel } from "./components/AuditPanel";
import { OperationsPanel } from "./components/OperationsPanel";
import { AdminUsersPanel } from "./components/AdminUsersPanel";
import { DocumentsIndex } from "./components/DocumentsIndex";
import { AnalyticsPanel } from "./components/AnalyticsPanel";
import { ImportsPanel } from "./components/ImportsPanel";
import { PermissionOverridesPanel } from "./components/PermissionOverridesPanel";
import { TimekeepingAdminPanel } from "./components/TimekeepingAdminPanel";

type Health = any;

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
  store_id: number;
};

type User = {
  id: number;
  username: string;
  email: string;
  store_id: number | null;
};

type NavItem = {
  id: string;
  label: string;
  permissions?: string[];
};

const navItems: NavItem[] = [
  { id: "overview", label: "Overview" },
  { id: "inventory", label: "Inventory", permissions: ["VIEW_INVENTORY", "RECEIVE_INVENTORY", "ADJUST_INVENTORY", "MANAGE_PRODUCTS"] },
  { id: "registers", label: "Registers", permissions: ["MANAGE_REGISTER", "CREATE_REGISTER"] },
  { id: "payments", label: "Payments", permissions: ["REFUND_PAYMENT", "VIEW_SALES_REPORTS"] },
  { id: "operations", label: "Operations", permissions: ["PROCESS_RETURN", "CREATE_TRANSFERS", "CREATE_COUNTS", "APPROVE_DOCUMENTS"] },
  { id: "documents", label: "Documents", permissions: ["VIEW_DOCUMENTS"] },
  { id: "analytics", label: "Analytics", permissions: ["VIEW_ANALYTICS"] },
  { id: "imports", label: "Imports", permissions: ["CREATE_IMPORTS"] },
  { id: "timekeeping", label: "Timekeeping", permissions: ["VIEW_TIMEKEEPING", "MANAGE_TIMEKEEPING"] },
  { id: "audits", label: "Audits", permissions: ["VIEW_AUDIT_LOG"] },
  { id: "users", label: "Users", permissions: ["VIEW_USERS", "CREATE_USER", "EDIT_USER"] },
  { id: "overrides", label: "Overrides", permissions: ["MANAGE_PERMISSIONS"] },
  { id: "auth", label: "Authentication" },
];

const pageCopy: Record<string, { title: string; description: string }> = {
  overview: {
    title: "Operations Suite",
    description: "Administrative oversight, documents, and inventory control.",
  },
  inventory: {
    title: "Inventory Control",
    description: "Manage products, receipts, adjustments, and ledger activity.",
  },
  registers: {
    title: "Register Management",
    description: "Open shifts, manage drawers, and audit register activity.",
  },
  payments: {
    title: "Payments Hub",
    description: "Collect tender, review balances, and handle voids.",
  },
  operations: {
    title: "Operational Documents",
    description: "Manage returns, transfers, and counts with audit-grade controls.",
  },
  documents: {
    title: "Documents Index",
    description: "Search and export posted documents across the store.",
  },
  analytics: {
    title: "Analytics",
    description: "Sales trends, inventory valuation, margin, and performance.",
  },
  imports: {
    title: "Imports",
    description: "Stage, map, and post data imports.",
  },
  timekeeping: {
    title: "Timekeeping",
    description: "Review time entries and approve corrections.",
  },
  audits: {
    title: "Audit Logs",
    description: "Review payment transactions and cash drawer events.",
  },
  auth: {
    title: "Authentication",
    description: "Manage users, sessions, and permissions entry points.",
  },
  users: {
    title: "User Management",
    description: "View users, assign roles, and manage account status.",
  },
  overrides: {
    title: "Permission Overrides",
    description: "Grant or deny permissions per user.",
  },
};

export function OperationsSuite({ onEnterRegisterMode }: { onEnterRegisterMode: () => void }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [invRefreshToken, setInvRefreshToken] = useState(0);
  const [asOf, setAsOf] = useState<string>("");
  const [activePage, setActivePage] = useState("overview");
  const [authVersion, setAuthVersion] = useState(0);
  const [authStatus, setAuthStatus] = useState<"unknown" | "authenticated" | "guest">("unknown");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [userPermissions, setUserPermissions] = useState<string[]>([]);
  const [storeId, setStoreId] = useState(1);

  async function load() {
    setErr(null);
    setLoadingProducts(true);
    try {
      const h = await apiGet<Health>("/health");
      setHealth(h);

      const p = await apiGet<{ items: Product[]; count: number }>(
        `/api/products?store_id=${storeId}`
      );
      setProducts(p.items);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to load");
    } finally {
      setLoadingProducts(false);
    }
  }

  async function loadSession() {
    const token = getAuthToken();
    if (!token) {
      setCurrentUser(null);
      setUserPermissions([]);
      setAuthStatus("guest");
      return;
    }
    try {
      const result = await apiPost<{ user: User; permissions?: string[] }>("/api/auth/validate", {});
      setCurrentUser(result.user);
      setUserPermissions(result.permissions ?? []);
      setAuthStatus("authenticated");
      if (result.user?.store_id && result.user.store_id !== storeId) {
        setStoreId(result.user.store_id);
      }
    } catch (e: any) {
      if ((e?.message ?? "").toLowerCase().includes("network")) {
        setAuthStatus("unknown");
        return;
      }
      clearAuthToken();
      setCurrentUser(null);
      setUserPermissions([]);
      setAuthStatus("guest");
    }
  }

  async function deleteProduct(id: number) {
    setErr(null);
    try {
      await apiDelete(`/api/products/${id}`);
      await load();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to delete product");
    }
  }

  async function updateProduct(
    id: number,
    patch: { name: string; price_cents: number | null; is_active: boolean }
  ) {
    setErr(null);
    try {
      await apiPut(`/api/products/${id}`, patch);
      await load();
    } catch (e: any) {
      setErr(e?.message ?? "Failed to update product");
    }
  }

  useEffect(() => {
    load();
  }, [storeId]);

  useEffect(() => {
    loadSession();
  }, [authVersion]);

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash && navItems.some((item) => item.id === hash)) {
      setActivePage(hash);
    }
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace("#", "");
      if (hash && navItems.some((item) => item.id === hash)) {
        setActivePage(hash);
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const stats = useMemo(() => {
    const total = products.length;
    const active = products.filter((product) => product.is_active).length;
    const priced = products.filter((product) => product.price_cents !== null).length;
    const avgPrice =
      priced === 0
        ? 0
        : Math.round(
            products.reduce((sum, product) => sum + (product.price_cents ?? 0), 0) / priced
          );

    return {
      total,
      active,
      inactive: total - active,
      avgPrice,
    };
  }, [products]);

  const visibleNavItems = useMemo(() => {
    return navItems.filter((item) => {
      if (!item.permissions || item.permissions.length === 0) {
        return true;
      }
      if (authStatus !== "authenticated") {
        return false;
      }
      return item.permissions.some((perm) => userPermissions.includes(perm));
    });
  }, [authStatus, userPermissions]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">APOS</span>
          <span className="brand__sub">Operations suite</span>
        </div>
        <nav className="nav">
          {visibleNavItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav__item ${item.id === activePage ? "nav__item--active" : ""}`}
              onClick={() => {
                setActivePage(item.id);
                window.location.hash = item.id;
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-card">
          <div className="sidebar-card__title">System health</div>
          <div className={`badge ${health ? "badge--good" : "badge--warn"}`}>
            {health ? "Healthy" : "Unknown"}
          </div>
          <div className="sidebar-card__meta">
            {health ? JSON.stringify(health) : "Awaiting backend handshake."}
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">Operations</div>
            <h1>{pageCopy[activePage]?.title ?? pageCopy.overview.title}</h1>
            <p className="muted">{pageCopy[activePage]?.description ?? pageCopy.overview.description}</p>
          </div>
          <div className="topbar__actions">
            <div className="field">
              <label>Store ID</label>
              <input
                className="input"
                type="number"
                min="1"
                value={storeId}
                onChange={(e) => setStoreId(Number(e.target.value))}
              />
            </div>
            <div className="chip">
              {authStatus === "authenticated" && currentUser
                ? `Signed in: ${currentUser.username}`
                : authStatus === "guest"
                  ? "Not signed in"
                  : "Checking session"}
            </div>
            <button className="btn btn--ghost" type="button" onClick={load}>
              Refresh
            </button>
            <button className="btn btn--primary" type="button" onClick={onEnterRegisterMode}>
              Enter Register Mode
            </button>
          </div>
        </header>

        {err && <div className="alert">{err}</div>}

        {activePage === "overview" && (
          <>
            <section className="stat-grid fade-in delay-1">
              <div className="stat-card">
                <div className="stat-card__title">Products</div>
                <div className="stat-card__value">{loadingProducts ? "--" : stats.total}</div>
                <div className="stat-card__meta">
                  {loadingProducts ? "Loading catalog" : `${stats.active} active items`}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card__title">Inactive</div>
                <div className="stat-card__value">{loadingProducts ? "--" : stats.inactive}</div>
                <div className="stat-card__meta">
                  {loadingProducts ? "Syncing statuses" : "Awaiting lifecycle updates"}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card__title">Avg. price</div>
                <div className="stat-card__value">
                  {loadingProducts ? "--" : `$${(stats.avgPrice / 100).toFixed(2)}`}
                </div>
                <div className="stat-card__meta">
                  {loadingProducts ? "Pricing sync in progress" : "Across priced SKUs"}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card__title">Inventory sync</div>
                <div className="stat-card__value">{loadingProducts ? "..." : "Live"}</div>
                <div className="stat-card__meta">Ledger refresh ready</div>
              </div>
            </section>

            <section className="content-grid fade-in delay-2">
              <div className="panel">
                <div className="panel__header">
                  <div>
                    <h2>Authentication</h2>
                    <p className="muted">Validate staff credentials and permissions.</p>
                  </div>
                </div>
                <AuthInterface onAuthChange={() => setAuthVersion((n) => n + 1)} storeId={storeId} />
              </div>
              <div className="panel">
                <div className="panel__header">
                  <div>
                    <h2>Identifier Lookup</h2>
                    <p className="muted">Quickly verify inventory identifiers.</p>
                  </div>
                </div>
                <IdentifierLookup />
              </div>
            </section>
          </>
        )}

        {activePage === "inventory" && (
          <>
            <section className="content-grid fade-in delay-2">
              <div className="panel panel--span-2">
                <div className="panel__header panel__header--split">
                  <div>
                    <h2>Inventory Controls</h2>
                    <p className="muted">Create products, receive inventory, and adjust stock.</p>
                  </div>
                  <div className="panel__actions">
                    <div className="field">
                      <label>As of</label>
                      <input
                        type="datetime-local"
                        value={asOf}
                        onChange={(e) => setAsOf(e.target.value)}
                        className="input"
                      />
                    </div>
                    <button
                      className="btn btn--ghost"
                      type="button"
                      onClick={() => setInvRefreshToken((n) => n + 1)}
                    >
                      Apply
                    </button>
                  </div>
                </div>
                {loadingProducts ? (
                  <div className="panel__placeholder">Loading inventory tools...</div>
                ) : (
                  <div className="panel__grid">
                    <div className="panel__section">
                      <CreateProductForm onCreated={load} />
                    </div>
                    <div className="panel__section">
                      <ReceiveInventoryForm
                        products={products}
                        storeId={storeId}
                        onReceived={async () => {
                          await load();
                          setInvRefreshToken((n) => n + 1);
                        }}
                      />
                    </div>
                    <div className="panel__section">
                      <AdjustInventoryForm
                        products={products}
                        storeId={storeId}
                        onAdjusted={async () => {
                          await load();
                          setInvRefreshToken((n) => n + 1);
                        }}
                      />
                    </div>
                    <div className="panel__section">
                      <LifecycleManager refreshToken={invRefreshToken} storeId={storeId} />
                    </div>
                  </div>
                )}
              </div>
            </section>

            <section className="content-grid fade-in delay-3">
              <div className="panel panel--wide">
                <div className="panel__header">
                  <div>
                    <h2>Inventory Ledger</h2>
                    <p className="muted">Trace adjustments and receipts across the store.</p>
                  </div>
                </div>
                <InventoryLedger
                  products={products}
                  refreshToken={invRefreshToken}
                  asOf={asOf}
                  storeId={storeId}
                />
              </div>
              <div className="panel panel--wide">
                <div className="panel__header">
                  <div>
                    <h2>Master Ledger</h2>
                    <p className="muted">Store-wide stock movement summary.</p>
                  </div>
                </div>
                <MasterLedger storeId={storeId} refreshToken={invRefreshToken} asOf={asOf} />
              </div>
            </section>

            <section className="content-grid fade-in delay-4">
              <div className="panel panel--full">
                <div className="panel__header">
                  <div>
                    <h2>Products Catalog</h2>
                    <p className="muted">Edit SKUs, pricing, and activity status.</p>
                  </div>
                </div>
                {loadingProducts ? (
                  <div className="panel__placeholder">Loading products...</div>
                ) : (
                  <ProductsTable
                    products={products}
                    onDelete={deleteProduct}
                    onUpdate={updateProduct}
                    asOf={asOf}
                    storeId={storeId}
                  />
                )}
              </div>
            </section>
          </>
        )}

        {activePage === "registers" && (
          <section className="content-grid fade-in delay-2">
            <RegistersPanel
              authVersion={authVersion}
              storeId={storeId}
              onStoreIdChange={setStoreId}
              isAuthed={authStatus === "authenticated"}
            />
          </section>
        )}

        {activePage === "payments" && (
          <section className="content-grid fade-in delay-2">
            <PaymentsPanel authVersion={authVersion} isAuthed={authStatus === "authenticated"} />
          </section>
        )}

        {activePage === "operations" && (
          <section className="content-grid fade-in delay-2">
            <OperationsPanel storeId={storeId} isAuthed={authStatus === "authenticated"} />
          </section>
        )}

        {activePage === "documents" && (
          <section className="content-grid fade-in delay-2">
            <DocumentsIndex storeId={storeId} />
          </section>
        )}

        {activePage === "analytics" && (
          <section className="content-grid fade-in delay-2">
            <AnalyticsPanel storeId={storeId} />
          </section>
        )}

        {activePage === "imports" && (
          <section className="content-grid fade-in delay-2">
            <ImportsPanel />
          </section>
        )}

        {activePage === "timekeeping" && (
          <section className="content-grid fade-in delay-2">
            <TimekeepingAdminPanel storeId={storeId} />
          </section>
        )}

        {activePage === "audits" && (
          <section className="content-grid fade-in delay-2">
            <AuditPanel authVersion={authVersion} isAuthed={authStatus === "authenticated"} />
          </section>
        )}

        {activePage === "users" && (
          <section className="content-grid fade-in delay-2">
            <AdminUsersPanel storeId={storeId} isAuthed={authStatus === "authenticated"} />
          </section>
        )}

        {activePage === "overrides" && (
          <section className="content-grid fade-in delay-2">
            <PermissionOverridesPanel />
          </section>
        )}

        {activePage === "auth" && (
          <section className="content-grid fade-in delay-2">
            <div className="panel panel--full">
              <div className="panel__header">
                <div>
                  <h2>Authentication</h2>
                  <p className="muted">Register users, create sessions, and initialize roles.</p>
                </div>
              </div>
              <AuthInterface onAuthChange={() => setAuthVersion((n) => n + 1)} storeId={storeId} />
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
