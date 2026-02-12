import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { api } from '@/lib/api';

export type Role = 'cashier' | 'manager' | 'admin';

interface AuthUser {
  id: number;
  username: string;
  name: string;
  email: string;
  role: Role;
  store_id: number | null;
  is_active: boolean;
  is_developer?: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  permissions: string[];
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  pinLogin: (pin: string, storeId?: number) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (minimum: Role) => boolean;
  hasPermission: (code: string) => boolean;
  isDeveloper: boolean;
  switchOrg: (orgId: number) => Promise<void>;
}

const roleLevel: Record<Role, number> = { cashier: 0, manager: 1, admin: 2 };

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = api.getToken();
    if (token) {
      api.post<{ user: AuthUser; permissions?: string[] }>('/api/auth/validate', {})
        .then((data) => {
          setUser(data.user);
          setPermissions(data.permissions ?? []);
        })
        .catch(() => {
          api.setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<{ token: string; user: AuthUser; permissions?: string[] }>('/api/auth/login', { username, password });
    api.setToken(data.token);
    setUser(data.user);
    setPermissions(data.permissions ?? []);
  }, []);

  const pinLogin = useCallback(async (pin: string, storeId?: number) => {
    const data = await api.post<{ token: string; user: AuthUser; permissions?: string[] }>('/api/auth/login-pin', { pin, store_id: storeId });
    api.setToken(data.token);
    setUser(data.user);
    setPermissions(data.permissions ?? []);
  }, []);

  const logout = useCallback(async () => {
    try { await api.post('/api/auth/logout', {}); } catch { /* ignore */ }
    api.setToken(null);
    setUser(null);
    setPermissions([]);
  }, []);

  const hasRole = useCallback((minimum: Role) => {
    if (!user) return false;
    return roleLevel[user.role] >= roleLevel[minimum];
  }, [user]);

  const hasPermission = useCallback((code: string) => {
    return permissions.includes(code);
  }, [permissions]);

  const isDeveloper = user?.is_developer ?? false;

  const switchOrg = useCallback(async (orgId: number) => {
    const data = await api.post<{ token: string; org_id: number; org_name: string; store_id: number | null; store_name: string | null }>('/api/developer/switch-org', { org_id: orgId });
    api.setToken(data.token);
    // Re-validate to refresh user info and permissions for the new org context
    const validated = await api.post<{ user: AuthUser; permissions?: string[] }>('/api/auth/validate', {});
    setUser(validated.user);
    setPermissions(validated.permissions ?? []);
  }, []);

  return (
    <AuthContext.Provider value={{ user, permissions, loading, login, pinLogin, logout, hasRole, hasPermission, isDeveloper, switchOrg }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
