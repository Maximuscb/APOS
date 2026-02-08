import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { WorkspaceSwitcher } from './WorkspaceSwitcher';
import { useAuth } from '@/context/AuthContext';
import { useStore } from '@/context/StoreContext';
import { Badge } from '@/components/ui/Badge';

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(id);
  }, []);
  return now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { currentStoreName, setStoreId, stores } = useStore();
  const navigate = useNavigate();
  const time = useClock();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-40 bg-white border-b border-border shadow-sm">
        <div className="flex items-center justify-between h-14 px-4 gap-3">
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-xs font-medium text-muted tabular-nums min-w-[4.5rem]">{time}</span>
            <span className="text-xl font-bold text-primary tracking-tight">APOS</span>
          </div>

          <div className="hidden sm:flex">
            <WorkspaceSwitcher />
          </div>

          <div className="flex items-center gap-2">
            {stores.length > 1 && (
              <select
                value={String(stores.find((s) => s.name === currentStoreName)?.id ?? '')}
                onChange={(e) => setStoreId(Number(e.target.value))}
                className="hidden lg:block h-9 px-2 rounded-xl border border-border bg-white text-sm cursor-pointer"
              >
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}

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

        <div className="sm:hidden px-4 pb-2">
          <WorkspaceSwitcher />
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
