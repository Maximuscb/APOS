import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import { useAuth } from '@/context/AuthContext';
import { useStore } from '@/context/StoreContext';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/lib/api';

interface OrgOption {
  id: number;
  name: string;
  code: string | null;
}

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(id);
  }, []);
  return {
    time: now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
    date: now.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
  };
}

export function AppShell() {
  const { user, logout, hasRole, isDeveloper, switchOrg } = useAuth();
  const { currentStoreId, currentStoreName, setStoreId, stores } = useStore();
  const navigate = useNavigate();
  const { time, date } = useClock();

  const [devOrgs, setDevOrgs] = useState<OrgOption[]>([]);
  const [currentOrgId, setCurrentOrgId] = useState<number | null>(null);

  // Fetch orgs list for developer users
  useEffect(() => {
    if (!isDeveloper) return;
    api.get<OrgOption[]>('/api/developer/organizations').then(setDevOrgs).catch(() => {});
    api.get<{ org_id: number | null }>('/api/developer/status').then((s) => setCurrentOrgId(s.org_id)).catch(() => {});
  }, [isDeveloper]);

  const handleOrgSwitch = async (orgId: number) => {
    await switchOrg(orgId);
    setCurrentOrgId(orgId);
    // Force page reload so StoreContext picks up the new stores
    window.location.reload();
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {isDeveloper && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-1 flex items-center gap-3 text-xs">
          <Badge variant="warning">DEV</Badge>
          <span className="text-amber-800 font-medium">Organization:</span>
          <select
            value={String(currentOrgId ?? '')}
            onChange={(e) => handleOrgSwitch(Number(e.target.value))}
            className="h-6 px-2 rounded border border-amber-300 bg-white text-xs text-amber-900 cursor-pointer"
          >
            {devOrgs.map((o) => (
              <option key={o.id} value={o.id}>{o.name}{o.code ? ` (${o.code})` : ''}</option>
            ))}
          </select>
        </div>
      )}
      <header className="sticky top-0 z-40 bg-white border-b border-border shadow-sm">
        <div className="flex items-center justify-between h-16 px-4 gap-3">
          <div className="flex items-center gap-3 shrink-0 min-w-0">
            <div className="h-9 w-9 rounded-xl bg-emerald-100 border border-emerald-200 flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="h-5 w-5 text-emerald-700" aria-hidden="true">
                <path
                  fill="currentColor"
                  d="M3 10.5 12 4l9 6.5v8a1.5 1.5 0 0 1-1.5 1.5H4.5A1.5 1.5 0 0 1 3 18.5v-8ZM6 18h3v-4h6v4h3v-6.2L12 7.4 6 11.8V18Z"
                />
              </svg>
            </div>
            <div className="flex flex-col leading-tight min-w-0">
              {hasRole('admin') && stores.length > 1 ? (
                <select
                  value={String(currentStoreId)}
                  onChange={(e) => setStoreId(Number(e.target.value))}
                  className="h-7 pl-0 pr-6 rounded-md bg-transparent text-sm font-semibold text-slate-900 cursor-pointer"
                >
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              ) : (
                <span className="text-sm font-semibold text-slate-900 truncate">{currentStoreName}</span>
              )}
              <span className="text-xs font-medium text-muted tabular-nums">{date}</span>
              <span className="text-xs font-medium text-muted tabular-nums">{time}</span>
            </div>
          </div>

          <div className="hidden sm:flex">
            <WorkspaceSwitcher />
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="primary">{user.role ?? 'user'}</Badge>
            <span className="text-sm text-zinc-600 hidden md:inline">{user.username}</span>

            <button
              onClick={handleLogout}
              className="h-9 px-3 rounded-xl border border-border bg-white text-sm text-zinc-600 hover:bg-zinc-50 cursor-pointer"
            >
              Logout
            </button>
          </div>
        </div>

      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
