import { useState, useEffect, useRef } from 'react';
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
  const { user, logout, isDeveloper, switchOrg } = useAuth();
  const { currentStoreName } = useStore();
  const navigate = useNavigate();
  const { time, date } = useClock();

  const [devOrgs, setDevOrgs] = useState<OrgOption[]>([]);
  const [currentOrgId, setCurrentOrgId] = useState<number | null>(null);
  const [orgPickerOpen, setOrgPickerOpen] = useState(false);
  const orgPickerRef = useRef<HTMLDivElement>(null);

  // Fetch orgs list for developer users
  useEffect(() => {
    if (!isDeveloper) return;
    api.get<OrgOption[]>('/api/developer/organizations').then(setDevOrgs).catch(() => {});
    api.get<{ org_id: number | null }>('/api/developer/status').then((s) => setCurrentOrgId(s.org_id)).catch(() => {});
  }, [isDeveloper]);

  // Close popover on outside click
  useEffect(() => {
    if (!orgPickerOpen) return;
    function handleClick(e: MouseEvent) {
      if (orgPickerRef.current && !orgPickerRef.current.contains(e.target as Node)) {
        setOrgPickerOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [orgPickerOpen]);

  const handleOrgSwitch = async (orgId: number) => {
    setOrgPickerOpen(false);
    await switchOrg(orgId);
    setCurrentOrgId(orgId);
    window.location.reload();
  };

  const currentOrg = devOrgs.find((o) => o.id === currentOrgId);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {isDeveloper && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 flex items-center gap-3 text-xs">
          <Badge variant="warning">DEV</Badge>
          <div ref={orgPickerRef} className="relative">
            <button
              onClick={() => setOrgPickerOpen((p) => !p)}
              className="h-7 px-3 rounded-lg border border-amber-300 bg-white text-xs font-medium text-amber-900 hover:bg-amber-100 cursor-pointer flex items-center gap-2"
            >
              <span className="truncate max-w-48">
                {currentOrg?.name ?? 'Select organization'}
              </span>
              <svg viewBox="0 0 20 20" fill="currentColor" className={`h-3.5 w-3.5 shrink-0 transition-transform ${orgPickerOpen ? 'rotate-180' : ''}`}>
                <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
              </svg>
            </button>

            {orgPickerOpen && (
              <div className="absolute left-0 top-full mt-1 w-64 bg-white rounded-xl border border-border shadow-lg z-50 py-1 max-h-72 overflow-y-auto">
                {devOrgs.length === 0 && (
                  <p className="px-3 py-2 text-xs text-muted">No organizations found.</p>
                )}
                {devOrgs.map((org) => {
                  const isActive = org.id === currentOrgId;
                  return (
                    <button
                      key={org.id}
                      onClick={() => handleOrgSwitch(org.id)}
                      disabled={isActive}
                      className={`w-full text-left px-3 py-2 flex items-center gap-2 text-sm cursor-pointer ${
                        isActive
                          ? 'bg-amber-50 text-amber-900'
                          : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <span className="w-4 shrink-0 text-amber-600">
                        {isActive ? '✓' : ''}
                      </span>
                      <span className="truncate font-medium">{org.name}</span>
                      {org.code && (
                        <Badge variant="muted" className="ml-auto shrink-0">{org.code}</Badge>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
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
              <span className="text-sm font-semibold text-slate-900 truncate">{currentStoreName}</span>
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
