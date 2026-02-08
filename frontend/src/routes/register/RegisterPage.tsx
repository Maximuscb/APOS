import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Tabs } from '@/components/ui/Tabs';
import { Input } from '@/components/ui/Input';

type Product = { id: number; sku: string; name: string; price_cents: number | null; store_id: number };
type Register = { id: number; register_number: string; name: string; location: string | null; current_session?: { id: number; status: string; user_id: number } | null };
type Sale = { id: number; document_number: string; status: string; store_id: number };
type SaleLine = { id: number; product_id: number; quantity: number; unit_price_cents: number; line_total_cents: number };
type Payment = { id: number; sale_id: number; tender_type: string; amount_cents: number; status: string };
type PaymentSummary = { total_due_cents: number; total_paid_cents: number; remaining_cents: number; change_due_cents: number; payment_status: string };
type TimekeepingStatus = { status: string; on_break: boolean; entry: { id: number } | null };

export function RegisterPage() {
  const { user, hasPermission } = useAuth();
  const { currentStoreId: storeId } = useStore();

  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [activeTab, setActiveTab] = useState('Sales');

  // Register session state
  const [registers, setRegisters] = useState<Register[]>([]);
  const [registerId, setRegisterId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [registerNumber, setRegisterNumber] = useState<string | null>(null);
  const [registerLoading, setRegisterLoading] = useState(true);
  const [showRegisterSelect, setShowRegisterSelect] = useState(false);

  // End shift modal
  const [showEndShiftModal, setShowEndShiftModal] = useState(false);
  const [showDrawerModal, setShowDrawerModal] = useState<'NO_SALE' | 'CASH_DROP' | null>(null);

  const [isFullscreen, setIsFullscreen] = useState(!!document.fullscreenElement);
  const hasManagerPermission = hasPermission('MANAGE_REGISTER');

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
    setLoadingProducts(true);
    try {
      const result = await api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
      setProducts(result.items ?? []);
    } finally {
      setLoadingProducts(false);
    }
  }

  async function initializeRegisterSession() {
    if (!user) return;
    setRegisterLoading(true);
    try {
      const result = await api.get<{ registers: Register[] }>(`/api/registers?store_id=${storeId}`);
      const regs = result.registers ?? [];
      setRegisters(regs);

      for (const reg of regs) {
        if (reg.current_session?.status === 'OPEN' && reg.current_session.user_id === user.id) {
          setRegisterId(reg.id);
          setSessionId(reg.current_session.id);
          setRegisterNumber(reg.register_number);
          setShowRegisterSelect(false);
          return;
        }
      }
      setShowRegisterSelect(true);
    } catch {
      setShowRegisterSelect(true);
    } finally {
      setRegisterLoading(false);
    }
  }

  function handleSessionStarted(regId: number, sessId: number, regNum: string) {
    setRegisterId(regId);
    setSessionId(sessId);
    setRegisterNumber(regNum);
    setShowRegisterSelect(false);
  }

  function handleShiftEnded() {
    setShowEndShiftModal(false);
    setRegisterId(null);
    setSessionId(null);
    setRegisterNumber(null);
    setShowRegisterSelect(true);
    initializeRegisterSession();
  }

  useEffect(() => {
    if (user) {
      loadProducts();
      initializeRegisterSession();
    }
  }, [user, storeId]);

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
            <Button variant="ghost" size="sm" onClick={toggleFullscreen}>
              {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
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
        <div className="mt-2">
          <Tabs tabs={['Sales', 'Payments', 'Timekeeping']} active={activeTab} onChange={setActiveTab} />
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'Sales' && (
          <SalesTab products={products} storeId={storeId} loadingProducts={loadingProducts} registerId={registerId} sessionId={sessionId} />
        )}
        {activeTab === 'Payments' && (
          <PaymentsTab registerId={registerId} sessionId={sessionId} />
        )}
        {activeTab === 'Timekeeping' && (
          <TimekeepingTab storeId={storeId} />
        )}
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

function SalesTab({ products, storeId, loadingProducts, registerId, sessionId }: {
  products: Product[];
  storeId: number;
  loadingProducts: boolean;
  registerId: number | null;
  sessionId: number | null;
}) {
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [lines, setLines] = useState<SaleLine[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function createNewSale() {
    setLoading(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { store_id: storeId };
      if (registerId) payload.register_id = registerId;
      if (sessionId) payload.register_session_id = sessionId;
      const result = await api.post<{ sale: Sale }>('/api/sales/', payload);
      setCurrentSale(result.sale);
      setLines([]);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to create sale');
    } finally {
      setLoading(false);
    }
  }

  async function addLineToSale() {
    if (!currentSale || !selectedProductId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<{ line: SaleLine }>(`/api/sales/${currentSale.id}/lines`, { product_id: selectedProductId, quantity });
      setLines((prev) => {
        const idx = prev.findIndex((l) => l.id === result.line.id);
        if (idx >= 0) { const updated = [...prev]; updated[idx] = result.line; return updated; }
        return [...prev, result.line];
      });
      setQuantity(1);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to add line');
    } finally {
      setLoading(false);
    }
  }

  async function postSale() {
    if (!currentSale) return;
    setLoading(true);
    setError(null);
    try {
      await api.post<{ sale: Sale }>(`/api/sales/${currentSale.id}/post`, {});
      setCurrentSale(null);
      setLines([]);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to post sale');
    } finally {
      setLoading(false);
    }
  }

  const total = lines.reduce((sum, l) => sum + l.line_total_cents, 0);

  if (loadingProducts) {
    return <div className="text-center text-muted py-8">Loading catalog...</div>;
  }

  if (!currentSale) {
    return (
      <div className="flex items-center justify-center py-16">
        <Card className="text-center max-w-sm">
          <CardTitle>Start a Sale</CardTitle>
          <CardDescription>Create a new sale to begin scanning items.</CardDescription>
          <div className="mt-4">
            <Button onClick={createNewSale} disabled={loading}>Open New Sale</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {error && <div className="lg:col-span-3 p-3 bg-red-50 text-red-700 text-sm rounded-xl">{error}</div>}

      {/* Left: Add items + cart */}
      <div className="lg:col-span-2 space-y-4">
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Badge variant="primary">{currentSale.status}</Badge>
            <Badge>{currentSale.document_number}</Badge>
          </div>
          <div className="flex gap-2 flex-wrap">
            <select
              className="h-11 px-3 rounded-xl border border-border bg-white text-sm flex-1 min-w-[200px]"
              value={selectedProductId ?? ''}
              onChange={(e) => setSelectedProductId(Number(e.target.value))}
            >
              <option value="">Select product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name} - {p.price_cents ? formatMoney(p.price_cents) : 'N/A'}</option>
              ))}
            </select>
            <input
              className="h-11 w-20 px-3 rounded-xl border border-border bg-white text-sm text-center"
              type="number" min="1" value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
            />
            <Button onClick={addLineToSale} disabled={loading || !selectedProductId}>Add Item</Button>
          </div>
        </Card>

        <Card padding={false}>
          <div className="grid grid-cols-4 gap-0 bg-slate-50 border-b border-border px-4 py-3 text-sm font-medium text-muted">
            <span>Item</span><span>Qty</span><span>Price</span><span className="text-right">Total</span>
          </div>
          {lines.length === 0 ? (
            <div className="px-4 py-8 text-center text-muted">No items in cart yet.</div>
          ) : lines.map((line) => {
            const prod = products.find((p) => p.id === line.product_id);
            return (
              <div key={line.id} className="grid grid-cols-4 gap-0 px-4 py-3 border-b border-border last:border-0 text-sm">
                <span className="font-medium">{prod?.name ?? 'Unknown'}</span>
                <span>{line.quantity}</span>
                <span>{formatMoney(line.unit_price_cents)}</span>
                <span className="text-right font-medium">{formatMoney(line.line_total_cents)}</span>
              </div>
            );
          })}
        </Card>
      </div>

      {/* Right: Summary */}
      <div className="space-y-4">
        <Card>
          <CardTitle>Order Summary</CardTitle>
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted">Items</span><span>{lines.reduce((s, l) => s + l.quantity, 0)}</span></div>
            <div className="flex justify-between"><span className="text-muted">Subtotal</span><span>{formatMoney(total)}</span></div>
            <div className="flex justify-between text-lg font-semibold border-t border-border pt-2 mt-2">
              <span>Total</span><span>{formatMoney(total)}</span>
            </div>
          </div>
          <p className="text-xs text-muted mt-3">Posting requires on-hand stock and a received cost basis for each item.</p>
          <div className="mt-4 space-y-2">
            <Button onClick={postSale} disabled={loading || lines.length === 0} className="w-full">Post Sale</Button>
            <Button variant="ghost" onClick={() => { setCurrentSale(null); setLines([]); }} className="w-full">Cancel Sale</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

// ─── Payments Tab ────────────────────────────────────────────────────────────

function PaymentsTab({ registerId, sessionId }: { registerId: number | null; sessionId: number | null }) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saleId, setSaleId] = useState('');
  const [includeVoided, setIncludeVoided] = useState(false);
  const [salePayments, setSalePayments] = useState<Payment[]>([]);
  const [saleSummary, setSaleSummary] = useState<PaymentSummary | null>(null);

  const [paymentForm, setPaymentForm] = useState({ sale_id: '', tender_type: 'CASH', amount_cents: 0, reference_number: '' });
  const [voidForm, setVoidForm] = useState({ payment_id: '', reason: '' });
  const [tenderSummary, setTenderSummary] = useState<Record<string, number> | null>(null);
  const [tenderSessionId, setTenderSessionId] = useState('');

  async function addPayment() {
    setLoading(true); setError(null);
    try {
      await api.post('/api/payments/', {
        sale_id: Number(paymentForm.sale_id), tender_type: paymentForm.tender_type,
        amount_cents: Number(paymentForm.amount_cents), reference_number: paymentForm.reference_number || null,
        register_id: registerId ?? null, register_session_id: sessionId ?? null,
      });
      setPaymentForm({ sale_id: '', tender_type: 'CASH', amount_cents: 0, reference_number: '' });
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  async function loadSalePayments() {
    if (!saleId) return;
    setLoading(true); setError(null);
    try {
      const result = await api.get<{ payments: Payment[]; summary: PaymentSummary }>(`/api/payments/sales/${saleId}?include_voided=${includeVoided}`);
      setSalePayments(result.payments ?? []);
      setSaleSummary(result.summary ?? null);
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  async function voidPayment() {
    if (!voidForm.payment_id) return;
    setLoading(true); setError(null);
    try {
      await api.post(`/api/payments/${voidForm.payment_id}/void`, { reason: voidForm.reason, register_id: registerId ?? null, register_session_id: sessionId ?? null });
      setVoidForm({ payment_id: '', reason: '' });
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  async function loadTenderSummary() {
    if (!tenderSessionId) return;
    setLoading(true); setError(null);
    try {
      const result = await api.get<{ tender_totals_cents: Record<string, number> }>(`/api/payments/sessions/${tenderSessionId}/tender-summary`);
      setTenderSummary(result.tender_totals_cents ?? null);
    } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  return (
    <div className="space-y-4">
      {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-xl">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardTitle>Add Payment</CardTitle>
          <div className="mt-3 space-y-3">
            <Input label="Sale ID" value={paymentForm.sale_id} onChange={(e) => setPaymentForm({ ...paymentForm, sale_id: e.target.value })} placeholder="Sale ID" />
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-700">Tender Type</label>
              <select className="h-11 px-3 rounded-xl border border-border bg-white text-sm" value={paymentForm.tender_type} onChange={(e) => setPaymentForm({ ...paymentForm, tender_type: e.target.value })}>
                <option value="CASH">CASH</option><option value="CARD">CARD</option><option value="CHECK">CHECK</option><option value="GIFT_CARD">GIFT_CARD</option><option value="STORE_CREDIT">STORE_CREDIT</option>
              </select>
            </div>
            <Input label="Amount (cents)" type="number" value={String(paymentForm.amount_cents)} onChange={(e) => setPaymentForm({ ...paymentForm, amount_cents: Number(e.target.value) })} />
            <Input label="Reference #" value={paymentForm.reference_number} onChange={(e) => setPaymentForm({ ...paymentForm, reference_number: e.target.value })} placeholder="Optional" />
            {(registerId || sessionId) && <p className="text-xs text-muted">Register: {registerId ?? 'N/A'} | Session: {sessionId ?? 'N/A'}</p>}
            <Button onClick={addPayment} disabled={loading} className="w-full">Add Payment</Button>
          </div>
        </Card>

        <Card>
          <CardTitle>Sale Payments</CardTitle>
          <div className="mt-3 space-y-3">
            <Input label="Sale ID" value={saleId} onChange={(e) => setSaleId(e.target.value)} placeholder="Sale ID" />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeVoided} onChange={(e) => setIncludeVoided(e.target.checked)} /> Include voided</label>
            <Button variant="secondary" onClick={loadSalePayments} disabled={loading} className="w-full">Load Payments</Button>
            {saleSummary && (
              <div className="bg-slate-50 rounded-xl p-3 space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-muted">Status</span><Badge>{saleSummary.payment_status}</Badge></div>
                <div className="flex justify-between"><span className="text-muted">Remaining</span><span>{formatMoney(saleSummary.remaining_cents)}</span></div>
                <div className="flex justify-between"><span className="text-muted">Change due</span><span>{formatMoney(saleSummary.change_due_cents)}</span></div>
              </div>
            )}
            {salePayments.length > 0 && (
              <div className="space-y-1">
                {salePayments.map((p) => (
                  <div key={p.id} className="flex justify-between text-sm p-2 bg-slate-50 rounded-lg">
                    <span>{p.tender_type} #{p.id}</span><span>{formatMoney(p.amount_cents)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardTitle>Void Payment</CardTitle>
          <div className="mt-3 space-y-3">
            <Input label="Payment ID" value={voidForm.payment_id} onChange={(e) => setVoidForm({ ...voidForm, payment_id: e.target.value })} />
            <Input label="Reason" value={voidForm.reason} onChange={(e) => setVoidForm({ ...voidForm, reason: e.target.value })} />
            <Button variant="danger" onClick={voidPayment} disabled={loading} className="w-full">Void Payment</Button>
          </div>
        </Card>

        <Card>
          <CardTitle>Tender Summary</CardTitle>
          <div className="mt-3 space-y-3">
            <Input label="Session ID" value={tenderSessionId} onChange={(e) => setTenderSessionId(e.target.value)} placeholder="Register session ID" />
            <Button variant="secondary" onClick={loadTenderSummary} disabled={loading} className="w-full">Load Tender Totals</Button>
            {tenderSummary && (
              <div className="space-y-1">
                {Object.entries(tenderSummary).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-sm p-2 bg-slate-50 rounded-lg"><span>{k}</span><span>{formatMoney(v)}</span></div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ─── Timekeeping Tab ─────────────────────────────────────────────────────────

function TimekeepingTab({ storeId }: { storeId: number }) {
  const [status, setStatus] = useState<TimekeepingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus() {
    try { const r = await api.get<TimekeepingStatus>('/api/timekeeping/status'); setStatus(r); } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); }
  }

  useEffect(() => { loadStatus(); }, []);

  async function doAction(endpoint: string, body: Record<string, unknown> = {}) {
    setLoading(true); setError(null);
    try { await api.post(endpoint, body); await loadStatus(); } catch (e: any) { setError(e?.detail || e?.message || 'Failed'); } finally { setLoading(false); }
  }

  return (
    <Card className="max-w-md">
      <div className="flex items-center justify-between mb-4">
        <CardTitle>Timekeeping</CardTitle>
        <Button variant="ghost" size="sm" onClick={loadStatus}>Refresh</Button>
      </div>
      {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-xl mb-3">{error}</div>}
      <div className="mb-4">
        <Badge variant={status?.status === 'clocked_in' ? 'success' : 'muted'}>{status?.status ?? 'Unknown'}</Badge>
        {status?.on_break && <Badge variant="warning" className="ml-2">On Break</Badge>}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button onClick={() => doAction('/api/timekeeping/clock-in', { store_id: storeId })} disabled={loading}>Clock In</Button>
        <Button variant="secondary" onClick={() => doAction('/api/timekeeping/clock-out')} disabled={loading}>Clock Out</Button>
        <Button variant="secondary" onClick={() => doAction('/api/timekeeping/break/start')} disabled={loading}>Start Break</Button>
        <Button variant="secondary" onClick={() => doAction('/api/timekeeping/break/end')} disabled={loading}>End Break</Button>
      </div>
    </Card>
  );
}

// ─── End Shift Dialog ────────────────────────────────────────────────────────

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
