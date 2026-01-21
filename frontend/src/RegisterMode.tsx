// Overview: Fullscreen Register Mode workflow with register selection and shift management.

import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { apiGet, apiPost, clearAuthToken, getAuthToken, setAuthToken } from "./lib/api";
import { appConfig } from "./lib/config";
import { SalesInterface } from "./components/SalesInterface";
import { PaymentsPanel } from "./components/PaymentsPanel";
import { PinLogin } from "./components/PinLogin";
import { TimekeepingPanel } from "./components/TimekeepingPanel";
import { RegisterSelectScreen } from "./components/RegisterSelectScreen";
import { EndShiftModal } from "./components/EndShiftModal";
import { DrawerEventModal } from "./components/DrawerEventModal";

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

type Register = {
  id: number;
  register_number: string;
  name: string;
  location: string | null;
  current_session?: { id: number; status: string; user_id: number } | null;
};

export function RegisterMode({ onExit }: { onExit: () => void }) {
  const [authStatus, setAuthStatus] = useState<"unknown" | "authenticated" | "guest">("unknown");
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [storeId, setStoreId] = useState(1);
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [activeTab, setActiveTab] = useState<"sales" | "payments" | "time">("sales");
  const [isFullscreen, setIsFullscreen] = useState(!!document.fullscreenElement);
  const [showFullscreenBanner, setShowFullscreenBanner] = useState(false);

  // Register session state
  const [registers, setRegisters] = useState<Register[]>([]);
  const [registerId, setRegisterId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [registerNumber, setRegisterNumber] = useState<string | null>(null);
  const [showRegisterSelect, setShowRegisterSelect] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(true);

  // Modal state
  const [showEndShiftModal, setShowEndShiftModal] = useState(false);
  const [showDrawerModal, setShowDrawerModal] = useState<"NO_SALE" | "CASH_DROP" | null>(null);

  const hasManagerPermission = permissions.includes("MANAGE_REGISTER");

  // Track fullscreen state via event listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await document.documentElement.requestFullscreen();
      }
    } catch (err) {
      console.error("Fullscreen toggle failed:", err);
    }
  }, []);

  const enterFullscreen = useCallback(async () => {
    try {
      await document.documentElement.requestFullscreen();
      setShowFullscreenBanner(false);
    } catch (err) {
      console.error("Fullscreen request failed:", err);
    }
  }, []);

  const dismissFullscreenBanner = useCallback(() => {
    setShowFullscreenBanner(false);
  }, []);

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

  async function initializeRegisterSession() {
    if (!user) return;

    setRegisterLoading(true);
    try {
      // Load registers for the store
      const result = await apiGet<{ registers: Register[] }>(`/api/registers?store_id=${storeId}`);
      const regs = result.registers ?? [];
      setRegisters(regs);

      // Check if user already has an open session on any register
      for (const reg of regs) {
        if (reg.current_session?.status === "OPEN" && reg.current_session.user_id === user.id) {
          // Found existing session - auto-select
          setRegisterId(reg.id);
          setSessionId(reg.current_session.id);
          setRegisterNumber(reg.register_number);
          setShowRegisterSelect(false);
          return;
        }
      }

      // No existing session - show register selection
      setShowRegisterSelect(true);
    } catch (err) {
      console.error("Failed to load registers:", err);
      setShowRegisterSelect(true);
    } finally {
      setRegisterLoading(false);
    }
  }

  function handleSessionStarted(regId: number, sessId: number, regNumber: string) {
    setRegisterId(regId);
    setSessionId(sessId);
    setRegisterNumber(regNumber);
    setShowRegisterSelect(false);
  }

  function handleShiftEnded() {
    setShowEndShiftModal(false);
    setRegisterId(null);
    setSessionId(null);
    setRegisterNumber(null);
    setShowRegisterSelect(true);
    // Reload registers to get updated session info
    initializeRegisterSession();
  }

  function handleSignOut() {
    clearAuthToken();
    setAuthStatus("guest");
    setUser(null);
    setPermissions([]);
    setRegisterId(null);
    setSessionId(null);
    setRegisterNumber(null);
    setShowRegisterSelect(false);
  }

  useEffect(() => {
    loadSession();
  }, []);

  useEffect(() => {
    if (authStatus === "authenticated" && user) {
      loadProducts();
      initializeRegisterSession();
    }
  }, [authStatus, storeId, user?.id]);

  // Show PIN login if not authenticated
  if (authStatus !== "authenticated") {
    return (
      <div className="register-shell">
        <PinLogin
          onSuccess={(token) => {
            setAuthToken(token);
            loadSession();
            if (!document.fullscreenElement) {
              setShowFullscreenBanner(true);
            }
          }}
          onFallback={() => onExit()}
        />
      </div>
    );
  }

  // Show loading while checking for existing session
  if (registerLoading) {
    return (
      <div className="register-shell">
        <div className="register-loading">
          <div className="register-loading__spinner" />
          <p>Loading registers...</p>
        </div>
      </div>
    );
  }

  // Show register selection if no active session
  if (showRegisterSelect || !sessionId) {
    return (
      <div className="register-shell">
        {showFullscreenBanner && appConfig.features.showFullscreenBanner && (
          <div className="fullscreen-banner">
            <span>For the best experience, use full screen mode.</span>
            <button className="btn btn--primary btn--sm" type="button" onClick={enterFullscreen}>
              Enter Full Screen
            </button>
            <button className="btn btn--ghost btn--sm" type="button" onClick={dismissFullscreenBanner}>
              Dismiss
            </button>
          </div>
        )}
        <RegisterSelectScreen
          registers={registers}
          userId={user?.id ?? 0}
          onSessionStarted={handleSessionStarted}
          onCancel={onExit}
        />
      </div>
    );
  }

  // Main register interface
  return (
    <div className="register-shell">
      <header className="register-header">
        <div>
          <div className="register-eyebrow">{appConfig.headerCopy.registerEyebrow}</div>
          <h1>{registerNumber ?? `Store ${storeId}`}</h1>
          <div className="register-meta">
            Signed in: {user?.username} | Session #{sessionId}
          </div>
        </div>
        <div className="register-actions">
          <button className="btn btn--ghost" type="button" onClick={toggleFullscreen}>
            {isFullscreen ? "Exit Full Screen" : "Enter Full Screen"}
          </button>
          <button
            className="btn btn--ghost"
            type="button"
            onClick={() => setShowDrawerModal("NO_SALE")}
            disabled={!hasManagerPermission}
            title={hasManagerPermission ? "Open drawer without a sale" : "Manager permission required"}
          >
            Open Drawer
          </button>
          <button
            className="btn btn--ghost"
            type="button"
            onClick={() => setShowDrawerModal("CASH_DROP")}
            disabled={!hasManagerPermission}
            title={hasManagerPermission ? "Remove cash from drawer" : "Manager permission required"}
          >
            Cash Drop
          </button>
          <button
            className="btn btn--warn"
            type="button"
            onClick={() => setShowEndShiftModal(true)}
          >
            End Shift
          </button>
          <button className="btn btn--ghost" type="button" onClick={handleSignOut}>
            Sign out
          </button>
          <button className="btn btn--primary" type="button" onClick={onExit}>
            Exit
          </button>
        </div>
      </header>

      {showFullscreenBanner && appConfig.features.showFullscreenBanner && (
        <div className="fullscreen-banner">
          <span>For the best experience, use full screen mode.</span>
          <button className="btn btn--primary btn--sm" type="button" onClick={enterFullscreen}>
            Enter Full Screen
          </button>
          <button className="btn btn--ghost btn--sm" type="button" onClick={dismissFullscreenBanner}>
            Dismiss
          </button>
        </div>
      )}

      <nav className="register-tabs">
        {appConfig.registerTabs.map((tab) => (
          <button
            key={tab.id}
            className={`register-tab ${activeTab === tab.id ? "register-tab--active" : ""}`}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="register-content">
        {activeTab === "sales" && (
          <div className="panel panel--full">
            {loadingProducts ? (
              <div className="panel__placeholder">Loading catalog...</div>
            ) : (
              <SalesInterface
                products={products}
                storeId={storeId}
                isAuthed={true}
                registerId={registerId}
                sessionId={sessionId}
              />
            )}
          </div>
        )}

        {activeTab === "payments" && (
          <div className="panel panel--full">
            <PaymentsPanel
              authVersion={0}
              isAuthed={true}
              registerId={registerId}
              sessionId={sessionId}
            />
          </div>
        )}

        {activeTab === "time" && (
          <div className="panel panel--full">
            <TimekeepingPanel storeId={storeId} />
          </div>
        )}
      </main>

      {/* End Shift Modal */}
      {showEndShiftModal && sessionId && registerNumber && (
        <EndShiftModal
          sessionId={sessionId}
          registerNumber={registerNumber}
          onClose={() => setShowEndShiftModal(false)}
          onShiftEnded={handleShiftEnded}
        />
      )}

      {/* Drawer Event Modal */}
      {showDrawerModal && sessionId && (
        <DrawerEventModal
          eventType={showDrawerModal}
          sessionId={sessionId}
          hasManagerPermission={hasManagerPermission}
          onClose={() => setShowDrawerModal(null)}
          onEventLogged={() => setShowDrawerModal(null)}
        />
      )}
    </div>
  );
}
