import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { loadState, saveState } from '@/lib/storage';
import { formatMoney } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { SalesWorkspace } from './SalesWorkspace';

type Product = { id: number; sku: string; name: string; price_cents: number | null; store_id: number };
type Register = { id: number; register_number: string; name: string; location: string | null; current_session?: { id: number; status: string; user_id: number } | null };
type TimekeepingStatus = { status: string; on_break: boolean; entry: { id: number } | null };
type SavedSession = { registerId: number; sessionId: number; registerNumber: string; storeId: number };

export function RegisterPage() {
  const { user, hasPermission } = useAuth();
  const { currentStoreId: storeId, stores, setStoreId } = useStore();

  const [products, setProducts] = useState<Product[]>([]);

  // Register session state — restore from localStorage for instant render on workspace switch
  const saved = loadState<SavedSession | null>('registerSession', null);
  const hasSaved = saved !== null && saved.storeId === storeId;
  const [registers, setRegisters] = useState<Register[]>([]);
  const [registerId, setRegisterId] = useState<number | null>(hasSaved ? saved.registerId : null);
  const [sessionId, setSessionId] = useState<number | null>(hasSaved ? saved.sessionId : null);
  const [registerNumber, setRegisterNumber] = useState<string | null>(hasSaved ? saved.registerNumber : null);
  const [registerLoading, setRegisterLoading] = useState(!hasSaved);
  const [showRegisterSelect, setShowRegisterSelect] = useState(false);

  // End shift modal
  const [showEndShiftModal, setShowEndShiftModal] = useState(false);
  const [showDrawerModal, setShowDrawerModal] = useState<'NO_SALE' | 'CASH_DROP' | null>(null);

  const [isFullscreen, setIsFullscreen] = useState(!!document.fullscreenElement);
  const hasManagerPermission = hasPermission('MANAGE_REGISTER');
  const [clockStatus, setClockStatus] = useState<TimekeepingStatus | null>(null);
  const [clockBusy, setClockBusy] = useState(false);
  const [clockError, setClockError] = useState<string | null>(null);
  const canSwitchStore = hasPermission('MANAGE_STORES') && stores.length > 1;
  const fullscreenAttempted = useRef(false);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch { /* ignore */ }
  }, []);

  async function loadProducts() {
    const result = await api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
    setProducts(result.items ?? []);
  }

  async function initializeRegisterSession() {
    if (!user) return;
    const hasExistingSession = registerId && sessionId;
    if (!hasExistingSession) setRegisterLoading(true);

    try {
      const result = await api.get<{ registers: Register[] }>(`/api/registers/?store_id=${storeId}`);
      const regs = result.registers ?? [];
      setRegisters(regs);

      for (const reg of regs) {
        if (reg.current_session?.status === 'OPEN' && reg.current_session.user_id === user.id) {
          setRegisterId(reg.id);
          setSessionId(reg.current_session.id);
          setRegisterNumber(reg.register_number);
          setShowRegisterSelect(false);
          saveState('registerSession', {
            registerId: reg.id,
            sessionId: reg.current_session.id,
            registerNumber: reg.register_number,
            storeId,
          });
          return;
        }
      }
      // No open session found — clear any stale saved state
      if (hasExistingSession) {
        setRegisterId(null);
        setSessionId(null);
        setRegisterNumber(null);
        saveState('registerSession', null);
      }
      setShowRegisterSelect(true);
    } catch {
      if (!hasExistingSession) setShowRegisterSelect(true);
    } finally {
      setRegisterLoading(false);
    }
  }

  function handleSessionStarted(regId: number, sessId: number, regNum: string) {
    setRegisterId(regId);
    setSessionId(sessId);
    setRegisterNumber(regNum);
    setShowRegisterSelect(false);
    saveState('registerSession', { registerId: regId, sessionId: sessId, registerNumber: regNum, storeId });
  }

  function handleShiftEnded() {
    setShowEndShiftModal(false);
    setRegisterId(null);
    setSessionId(null);
    setRegisterNumber(null);
    setShowRegisterSelect(true);
    saveState('registerSession', null);
    initializeRegisterSession();
  }

  useEffect(() => {
    if (user) {
      loadProducts();
      initializeRegisterSession();
      loadClockStatus();
    }
  }, [user, storeId]);

  useEffect(() => {
    if (!sessionId || fullscreenAttempted.current || document.fullscreenElement) return;
    fullscreenAttempted.current = true;
    document.documentElement.requestFullscreen().catch(() => {});
  }, [sessionId]);

  async function loadClockStatus() {
    try {
      const r = await api.get<TimekeepingStatus>('/api/timekeeping/status');
      setClockStatus(r);
    } catch {
      setClockStatus(null);
    }
  }

  async function toggleClock() {
    setClockBusy(true);
    setClockError(null);
    try {
      const status = (clockStatus?.status ?? '').toUpperCase();
      const isClockedIn = status === 'CLOCKED_IN' || status === 'ON_BREAK';
      if (isClockedIn) {
        await api.post('/api/timekeeping/clock-out', {});
      } else {
        await api.post('/api/timekeeping/clock-in', { store_id: storeId });
      }
      await loadClockStatus();
    } catch (e: any) {
      setClockError(e?.detail || e?.message || 'Unable to update clock status.');
    } finally {
      setClockBusy(false);
    }
  }

  async function clockOutFromWorkspace() {
    setClockBusy(true);
    setClockError(null);
    try {
      await api.post('/api/timekeeping/clock-out', {});
      await loadClockStatus();
    } catch (e: any) {
      const message = e?.detail || e?.message || 'Unable to clock out.';
      setClockError(message);
      throw e;
    } finally {
      setClockBusy(false);
    }
  }

  if (registerLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-muted">Loading registers...</p>
        </div>
      </div>
    );
  }

  if (showRegisterSelect || !sessionId) {
    return <RegisterSelectView registers={registers} userId={user?.id ?? 0} onSessionStarted={handleSessionStarted} />;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Register header */}
      <div className="bg-white border-b border-border px-4 py-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold">{registerNumber}</span>
            <Badge variant="success">Session #{sessionId}</Badge>
            <span className="text-sm text-muted">{user?.username}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {canSwitchStore && (
              <select
                value={String(storeId)}
                onChange={(e) => setStoreId(Number(e.target.value))}
                className="h-9 px-2 rounded-xl border border-border bg-white text-sm cursor-pointer"
              >
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
            <Button variant="ghost" size="sm" onClick={toggleFullscreen}>
              {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            </Button>
            <Button variant="ghost" size="sm" onClick={toggleClock} disabled={clockBusy}>
              {clockBusy
                ? 'Working...'
                : ((clockStatus?.status ?? '').toUpperCase() === 'CLOCKED_IN' || (clockStatus?.status ?? '').toUpperCase() === 'ON_BREAK')
                  ? 'Clock Out'
                  : 'Clock In'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowDrawerModal('NO_SALE')} disabled={!hasManagerPermission} title={hasManagerPermission ? 'Open drawer' : 'Manager required'}>
              Open Drawer
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowDrawerModal('CASH_DROP')} disabled={!hasManagerPermission} title={hasManagerPermission ? 'Cash drop' : 'Manager required'}>
              Cash Drop
            </Button>
            <Button variant="warning" size="sm" onClick={() => setShowEndShiftModal(true)}>
              End Shift
            </Button>
          </div>
        </div>
        {clockError && (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {clockError}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <SalesWorkspace
          userId={user?.id ?? 0}
          storeId={storeId}
          products={products}
          registerId={registerId}
          sessionId={sessionId}
          clockStatus={clockStatus?.status ?? null}
          clockBusy={clockBusy}
          onClockOut={clockOutFromWorkspace}
        />
      </div>

      {/* End Shift Modal */}
      {showEndShiftModal && sessionId && registerNumber && (
        <EndShiftDialog sessionId={sessionId} registerNumber={registerNumber} onClose={() => setShowEndShiftModal(false)} onShiftEnded={handleShiftEnded} />
      )}

      {/* Drawer Event Modal */}
      {showDrawerModal && sessionId && (
        <DrawerEventDialog eventType={showDrawerModal} sessionId={sessionId} hasManagerPermission={hasManagerPermission} onClose={() => setShowDrawerModal(null)} onEventLogged={() => setShowDrawerModal(null)} />
      )}
    </div>
  );
}

// ─── Register Select ─────────────────────────────────────────────────────────

function RegisterSelectView({ registers, userId, onSessionStarted }: {
  registers: Register[];
  userId: number;
  onSessionStarted: (regId: number, sessId: number, regNum: string) => void;
}) {
  const [selectedRegisterId, setSelectedRegisterId] = useState<number | null>(null);
  const [openingCash, setOpeningCash] = useState('100.00');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRegister = registers.find((r) => r.id === selectedRegisterId);
  const hasOtherUserSession = selectedRegister?.current_session && selectedRegister.current_session.user_id !== userId;

  async function handleOpenShift() {
    if (!selectedRegisterId) { setError('Select a register.'); return; }
    if (hasOtherUserSession) { setError('Register in use by another user.'); return; }
    const opening_cash_cents = Math.round(Number(openingCash) * 100);
    if (!Number.isFinite(opening_cash_cents) || opening_cash_cents < 0) { setError('Invalid opening cash.'); return; }

    setLoading(true);
    setError(null);
    try {
      const result = await api.post<{ session: { id: number } }>(`/api/registers/${selectedRegisterId}/shifts/open`, { opening_cash_cents });
      const reg = registers.find((r) => r.id === selectedRegisterId);
      onSessionStarted(selectedRegisterId, result.session.id, reg?.register_number ?? '');
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to open shift.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center h-[calc(100vh-3.5rem)] p-4">
      <Card className="w-full max-w-lg">
        <CardTitle>Select Register</CardTitle>
        <CardDescription>Choose a register to open your shift.</CardDescription>

        {error && <div className="mt-3 p-3 bg-red-50 text-red-700 text-sm rounded-xl">{error}</div>}

        <div className="mt-4 space-y-2">
          {registers.length === 0 ? (
            <p className="text-muted py-4 text-center">No registers available for this store.</p>
          ) : registers.map((reg) => {
            const hasSession = reg.current_session?.status === 'OPEN';
            const isOwnSession = hasSession && reg.current_session?.user_id === userId;
            const isOtherSession = hasSession && !isOwnSession;

            return (
              <button
                key={reg.id}
                onClick={() => setSelectedRegisterId(reg.id)}
                disabled={isOtherSession}
                className={`w-full flex items-center justify-between p-3 rounded-xl border transition-colors cursor-pointer
                  ${selectedRegisterId === reg.id ? 'border-primary bg-primary-light' : 'border-border hover:bg-slate-50'}
                  ${isOtherSession ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="text-left">
                  <div className="font-medium">{reg.register_number}</div>
                  <div className="text-sm text-muted">{reg.name}</div>
                </div>
                <div>
                  {isOwnSession && <Badge variant="success">Your session</Badge>}
                  {isOtherSession && <Badge variant="warning">In use</Badge>}
                  {!hasSession && <Badge variant="muted">Available</Badge>}
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-4">
          <Input label="Opening Cash (USD)" type="text" inputMode="decimal" value={openingCash} onChange={(e) => setOpeningCash(e.target.value)} placeholder="100.00" />
        </div>

        <div className="mt-4 flex gap-2">
          <Button onClick={handleOpenShift} disabled={loading || !selectedRegisterId} className="flex-1">
            {loading ? 'Opening...' : 'Open Shift'}
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ─── Sales Tab ───────────────────────────────────────────────────────────────

function EndShiftDialog({ sessionId, registerNumber, onClose, onShiftEnded }: {
  sessionId: number; registerNumber: string; onClose: () => void; onShiftEnded: () => void;
}) {
  const [closingCash, setClosingCash] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ session: { closing_cash_cents: number; expected_cash_cents: number | null; variance_cents: number | null } } | null>(null);

  async function handleCloseShift() {
    const closing_cash_cents = Math.round(Number(closingCash) * 100);
    if (!Number.isFinite(closing_cash_cents) || closing_cash_cents < 0) { setError('Enter a valid closing cash amount.'); return; }
    setLoading(true); setError(null);
    try {
      const res = await api.post<typeof result>(`/api/registers/sessions/${sessionId}/close`, { closing_cash_cents, notes: notes || null });
      setResult(res);
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed to close shift.'); } finally { setLoading(false); }
  }

  if (result) {
    const v = result.session.variance_cents;
    return (
      <Dialog open={true} onClose={onShiftEnded} title="Shift Closed">
        <div className="space-y-3 text-sm">
          <div className="flex justify-between"><span className="text-muted">Register</span><span>{registerNumber}</span></div>
          <div className="flex justify-between"><span className="text-muted">Closing Cash</span><span>{formatMoney(result.session.closing_cash_cents)}</span></div>
          <div className="flex justify-between"><span className="text-muted">Expected Cash</span><span>{result.session.expected_cash_cents != null ? formatMoney(result.session.expected_cash_cents) : '--'}</span></div>
          <div className={`flex justify-between font-medium ${v != null && v < 0 ? 'text-red-600' : v != null && v > 0 ? 'text-emerald-600' : ''}`}>
            <span>Variance</span>
            <span>{v != null ? (v >= 0 ? `+${formatMoney(v)} (over)` : `${formatMoney(v)} (short)`) : '--'}</span>
          </div>
        </div>
        <div className="mt-4"><Button onClick={onShiftEnded} className="w-full">Done</Button></div>
      </Dialog>
    );
  }

  return (
    <Dialog open={true} onClose={onClose} title="End Shift">
      <p className="text-sm text-muted mb-4">Count the cash drawer and close the shift on {registerNumber}.</p>
      {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-xl mb-3">{error}</div>}
      <div className="space-y-3">
        <Input label="Closing Cash (USD)" type="text" inputMode="decimal" value={closingCash} onChange={(e) => setClosingCash(e.target.value)} placeholder="0.00" />
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-slate-700">Notes (optional)</label>
          <textarea className="px-3 py-2 rounded-xl border border-border bg-white text-sm placeholder:text-slate-400 focus:outline-2 focus:outline-primary" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Any notes about this shift..." />
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={handleCloseShift} disabled={loading || !closingCash} className="flex-1">{loading ? 'Closing...' : 'Close Shift'}</Button>
        <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
      </div>
    </Dialog>
  );
}

// ─── Drawer Event Dialog ─────────────────────────────────────────────────────

function DrawerEventDialog({ eventType, sessionId, hasManagerPermission, onClose, onEventLogged }: {
  eventType: 'NO_SALE' | 'CASH_DROP'; sessionId: number; hasManagerPermission: boolean; onClose: () => void; onEventLogged: () => void;
}) {
  const [reason, setReason] = useState('');
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isNoSale = eventType === 'NO_SALE';

  async function handleSubmit() {
    if (!reason.trim()) { setError('Please provide a reason.'); return; }
    if (!isNoSale) { const c = Math.round(Number(amount) * 100); if (!Number.isFinite(c) || c <= 0) { setError('Enter a valid amount > $0.'); return; } }
    setLoading(true); setError(null);
    try {
      if (isNoSale) await api.post(`/api/registers/sessions/${sessionId}/drawer/no-sale`, { reason: reason.trim() });
      else await api.post(`/api/registers/sessions/${sessionId}/drawer/cash-drop`, { amount_cents: Math.round(Number(amount) * 100), reason: reason.trim() });
      onEventLogged();
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  return (
    <Dialog open={true} onClose={onClose} title={isNoSale ? 'Open Drawer (No Sale)' : 'Cash Drop'}>
      <p className="text-sm text-muted mb-4">{isNoSale ? 'Open the cash drawer without processing a sale.' : 'Remove excess cash from the drawer.'}</p>
      {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-xl mb-3">{error}</div>}
      {!hasManagerPermission && <div className="p-3 bg-amber-50 text-amber-700 text-sm rounded-xl mb-3">Manager approval required.</div>}
      <div className="space-y-3">
        {!isNoSale && <Input label="Amount to Remove (USD)" type="text" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />}
        <Input label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={isNoSale ? 'e.g., Customer needed change' : 'e.g., Safe drop'} />
      </div>
      <div className="mt-4 flex gap-2">
        <Button onClick={handleSubmit} disabled={loading || !reason.trim() || (!isNoSale && !amount) || !hasManagerPermission} className="flex-1">
          {loading ? 'Processing...' : isNoSale ? 'Open Drawer' : 'Log Cash Drop'}
        </Button>
        <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
      </div>
    </Dialog>
  );
}

