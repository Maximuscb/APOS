import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { api } from '@/lib/api';

interface ActiveNotification {
  kind: 'ANNOUNCEMENT' | 'REMINDER';
  id: number;
  title: string;
  body: string;
  priority: string;
}

const priorityVariant: Record<string, 'default' | 'primary' | 'warning' | 'danger'> = {
  LOW: 'default',
  NORMAL: 'primary',
  HIGH: 'warning',
  URGENT: 'danger',
};

export function LoginPage() {
  const { login, pinLogin } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'password' | 'pin'>('password');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Post-login announcements
  const [notifications, setNotifications] = useState<ActiveNotification[]>([]);
  const [showPopup, setShowPopup] = useState(false);

  async function fetchActiveComms() {
    try {
      const res = await api.get<{ notifications: ActiveNotification[] }>(
        '/api/communications/active',
      );
      const n = res.notifications ?? [];
      if (n.length > 0) {
        setNotifications(n);
        setShowPopup(true);
        return true;
      }
    } catch {
      // Non-critical — don't block login
    }
    return false;
  }

  async function dismissPopup() {
    await Promise.all(
      notifications.map((n) =>
        api.post(`/api/communications/notifications/${n.kind}/${n.id}/dismiss`, {}).catch(() => undefined),
      ),
    );
    setShowPopup(false);
    navigate('/sales', { replace: true });
  }

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      const hasComms = await fetchActiveComms();
      if (!hasComms) navigate('/sales', { replace: true });
    } catch (err: any) {
      setError(err.detail || err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handlePinLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await pinLogin(pin);
      const hasComms = await fetchActiveComms();
      if (!hasComms) navigate('/sales', { replace: true });
    } catch (err: any) {
      setError(err.detail || err.message || 'PIN login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm p-8 bg-white rounded-2xl shadow-md border border-border">
        <h1 className="text-2xl font-bold text-center mb-1">APOS</h1>
        <p className="text-sm text-muted text-center mb-6">Advanced Point-of-Sale System</p>

        <div className="flex gap-1 mb-6 bg-slate-100 rounded-xl p-1">
          <button
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${mode === 'password' ? 'bg-white text-slate-900 shadow-sm' : 'text-muted hover:text-slate-700'}`}
            onClick={() => setMode('password')}
          >
            Username & Password
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${mode === 'pin' ? 'bg-white text-slate-900 shadow-sm' : 'text-muted hover:text-slate-700'}`}
            onClick={() => setMode('pin')}
          >
            PIN
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-xl">
            {error}
          </div>
        )}

        {mode === 'password' ? (
          <form onSubmit={handlePasswordLogin} className="space-y-4">
            <Input
              label="Username or Email"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username or email"
            />
            <Input
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              type="password"
            />
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        ) : (
          <form onSubmit={handlePinLogin} className="space-y-4">
            <Input
              label="PIN"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="Enter PIN"
              maxLength={6}
              className="text-center text-2xl tracking-widest"
            />
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In with PIN'}
            </Button>
          </form>
        )}

        <p className="mt-4 text-xs text-muted text-center">
          Need an account? Contact an administrator.
        </p>
      </div>

      {/* Post-login announcements/reminders popup */}
      <Dialog open={showPopup} onClose={dismissPopup} title="Notifications">
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          <div className="space-y-3">
            {notifications.map((n) => (
              <div key={`${n.kind}-${n.id}`} className="rounded-xl border border-border p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={n.kind === 'REMINDER' ? 'warning' : 'primary'}>{n.kind}</Badge>
                  {n.kind === 'ANNOUNCEMENT' && (
                    <Badge variant={priorityVariant[n.priority] ?? 'default'}>{n.priority}</Badge>
                  )}
                </div>
                <h3 className="font-semibold text-slate-900 text-sm">{n.title}</h3>
                {n.body && <p className="text-sm text-muted mt-1">{n.body}</p>}
              </div>
            ))}
          </div>
          <div className="flex justify-end pt-2">
            <Button onClick={dismissPopup}>Acknowledge</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
