import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ReturnsPanel } from './ReturnsPanel';

type Product = { id: number; sku: string; name: string; price_cents: number | null; store_id: number };
type Sale = { id: number; document_number: string; status: string; store_id: number };
type SaleLine = { id: number; product_id: number; quantity: number; unit_price_cents: number; line_total_cents: number };
type TaskRow = { id: number; document_type: string; document_number: string; status: string };
type CommTask = { id: number; title: string; description: string | null; status: string; task_type: string };
type QuickScreen = { id: string; name: string; product_ids: number[] };
type Announcement = { id: number; title: string; body: string; priority: string; is_active: boolean };
type Reminder = { id: number; title: string; body: string; is_active: boolean; repeat_type: string };
type Payment = { id: number; tender_type: string; amount_cents: number; change_cents: number; status: string };
type PaymentSummary = {
  total_due_cents: number | null;
  total_paid_cents: number | null;
  remaining_cents: number | null;
  change_due_cents: number | null;
  payment_status: string | null;
  payments: Payment[];
};

function keyForUser(userId: number) {
  return `sales_quick_screens_${userId}`;
}

function defaultScreens(products: Product[]): QuickScreen[] {
  const ids = products.map((p) => p.id);
  return [
    { id: 'screen-1', name: 'Screen 1', product_ids: ids.slice(0, 24) },
    { id: 'screen-2', name: 'Screen 2', product_ids: ids.slice(24, 48) },
  ];
}

const tenderOptions = ['CASH', 'CARD', 'CHECK', 'GIFT_CARD', 'STORE_CREDIT'] as const;
type TenderType = (typeof tenderOptions)[number];

function getErrorMessage(e: any, fallback: string) {
  return e?.detail || e?.message || fallback;
}

export function SalesWorkspace({
  userId,
  storeId,
  products,
  registerId,
  sessionId,
}: {
  userId: number;
  storeId: number;
  products: Product[];
  registerId: number | null;
  sessionId: number;
}) {
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [lines, setLines] = useState<SaleLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [commTasks, setCommTasks] = useState<CommTask[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);

  const [paymentSummary, setPaymentSummary] = useState<PaymentSummary | null>(null);
  const [paymentTender, setPaymentTender] = useState<TenderType>('CASH');
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentRef, setPaymentRef] = useState('');
  const [paymentBusy, setPaymentBusy] = useState(false);

  const [screens, setScreens] = useState<QuickScreen[]>([]);
  const [activeScreenId, setActiveScreenId] = useState('');
  const [selectedProductToAdd, setSelectedProductToAdd] = useState('');
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [mode, setMode] = useState<'quick' | 'returns'>('quick');

  const productById = useMemo(() => {
    const map = new Map<number, Product>();
    products.forEach((p) => map.set(p.id, p));
    return map;
  }, [products]);

  const activeScreen = useMemo(() => screens.find((s) => s.id === activeScreenId) ?? null, [screens, activeScreenId]);
  const quickProducts = useMemo(() => (activeScreen?.product_ids ?? []).map((id) => productById.get(id)).filter((p): p is Product => !!p), [activeScreen, productById]);

  function resetPaymentInputs() {
    setPaymentAmount('');
    setPaymentRef('');
  }

  useEffect(() => {
    const raw = localStorage.getItem(keyForUser(userId));
    if (!raw) {
      const defaults = defaultScreens(products);
      setScreens(defaults);
      setActiveScreenId(defaults[0]?.id ?? '');
      return;
    }
    try {
      const parsed = JSON.parse(raw) as QuickScreen[];
      const validIds = new Set(products.map((p) => p.id));
      const normalized = parsed.map((s, idx) => ({
        id: s.id || `screen-${idx + 1}`,
        name: s.name || `Screen ${idx + 1}`,
        product_ids: (s.product_ids ?? []).filter((id) => validIds.has(id)),
      }));
      setScreens(normalized.length > 0 ? normalized : defaultScreens(products));
      setActiveScreenId((normalized[0]?.id) || 'screen-1');
    } catch {
      const defaults = defaultScreens(products);
      setScreens(defaults);
      setActiveScreenId(defaults[0]?.id ?? '');
    }
  }, [userId, products]);

  useEffect(() => {
    if (screens.length > 0) {
      localStorage.setItem(keyForUser(userId), JSON.stringify(screens));
    }
  }, [screens, userId]);

  useEffect(() => {
    if (!activeScreenId && screens.length > 0) setActiveScreenId(screens[0].id);
  }, [activeScreenId, screens]);

  async function createNewSale() {
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { store_id: storeId, register_session_id: sessionId };
      if (registerId) payload.register_id = registerId;
      const res = await api.post<{ sale: Sale }>('/api/sales/', payload);
      setCurrentSale(res.sale);
      setLines([]);
      setPaymentSummary(null);
      resetPaymentInputs();
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to create sale.'));
    } finally {
      setBusy(false);
    }
  }

  async function loadSale() {
    if (!currentSale) return;
    try {
      const res = await api.get<{ sale: Sale; lines: SaleLine[] }>(`/api/sales/${currentSale.id}`);
      setCurrentSale(res.sale);
      setLines(res.lines ?? []);
    } catch {
      // ignore
    }
  }

  async function loadPaymentSummary(saleId: number) {
    try {
      const res = await api.get<PaymentSummary>(`/api/payments/sales/${saleId}/summary`);
      setPaymentSummary(res);
    } catch {
      setPaymentSummary(null);
    }
  }

  useEffect(() => {
    if (!currentSale && !busy) createNewSale();
  }, [currentSale, busy]);

  useEffect(() => {
    if (currentSale) {
      loadPaymentSummary(currentSale.id);
    }
  }, [currentSale?.id]);

  async function addProduct(productId: number) {
    if (!currentSale) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ line: SaleLine }>(`/api/sales/${currentSale.id}/lines`, { product_id: productId, quantity: 1 });
      setLines((prev) => {
        const idx = prev.findIndex((l) => l.id === res.line.id);
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = res.line;
          return copy;
        }
        return [...prev, res.line];
      });
      await loadPaymentSummary(currentSale.id);
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to add item.'));
    } finally {
      setBusy(false);
    }
  }

  async function postSale() {
    if (!currentSale) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/sales/${currentSale.id}/post`, {});
      await loadSale();
      await loadPaymentSummary(currentSale.id);
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to post sale.'));
    } finally {
      setBusy(false);
    }
  }

  async function applyPayment() {
    if (!currentSale) return;
    const amountCents = Math.round(Number(paymentAmount) * 100);
    if (!Number.isFinite(amountCents) || amountCents <= 0) {
      setError('Enter a valid payment amount.');
      return;
    }

    setPaymentBusy(true);
    setError(null);
    try {
      await api.post('/api/payments/', {
        sale_id: currentSale.id,
        tender_type: paymentTender,
        amount_cents: amountCents,
        reference_number: paymentRef.trim() || undefined,
        register_id: registerId ?? undefined,
        register_session_id: sessionId,
      });
      resetPaymentInputs();
      await loadSale();
      await loadPaymentSummary(currentSale.id);
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to apply payment.'));
    } finally {
      setPaymentBusy(false);
    }
  }

  async function loadTasks() {
    setTasksLoading(true);
    try {
      const [docRes, commRes, activeRes] = await Promise.all([
        api.get<{ documents?: TaskRow[] }>(`/api/documents?store_id=${storeId}&status=APPROVED`),
        api.get<CommTask[]>(`/api/communications/tasks?store_id=${storeId}`).catch(() => [] as CommTask[]),
        api.get<{ announcements?: Announcement[]; reminders?: Reminder[] }>(`/api/communications/active?store_id=${storeId}`).catch(() => ({ announcements: [], reminders: [] })),
      ]);
      setTasks((docRes.documents ?? []).slice(0, 10));
      setCommTasks(commRes.filter((t) => t.status === 'PENDING'));
      setAnnouncements((activeRes.announcements ?? []).filter((a) => a.is_active).slice(0, 5));
      setReminders((activeRes.reminders ?? []).filter((r) => r.is_active).slice(0, 5));
    } catch {
      setTasks([]);
      setCommTasks([]);
      setAnnouncements([]);
      setReminders([]);
    } finally {
      setTasksLoading(false);
    }
  }

  async function completeCommTask(taskId: number) {
    try {
      await api.patch(`/api/communications/tasks/${taskId}`, { status: 'COMPLETED' });
      loadTasks();
    } catch { /* silent */ }
  }

  async function deferCommTask(taskId: number) {
    try {
      await api.patch(`/api/communications/tasks/${taskId}`, { status: 'DEFERRED' });
      loadTasks();
    } catch { /* silent */ }
  }

  useEffect(() => {
    loadTasks();
  }, [storeId, userId]);

  const itemCount = lines.reduce((sum, l) => sum + l.quantity, 0);
  const totalCents = lines.reduce((sum, l) => sum + l.line_total_cents, 0);
  const remainingCents = paymentSummary?.remaining_cents ?? totalCents;
  const isPaid = paymentSummary?.remaining_cents !== null && paymentSummary?.remaining_cents !== undefined && paymentSummary.remaining_cents <= 0;

  return (
    <div className="h-full grid grid-cols-1 xl:grid-cols-12 gap-4">
      <div className="xl:col-span-12 flex gap-2">
        <button onClick={() => setMode('quick')} className={`px-3 h-9 rounded-lg text-sm font-medium ${mode === 'quick' ? 'bg-primary-light text-primary' : 'bg-slate-100 text-slate-600'}`}>Sales</button>
        <button onClick={() => setMode('returns')} className={`px-3 h-9 rounded-lg text-sm font-medium ${mode === 'returns' ? 'bg-primary-light text-primary' : 'bg-slate-100 text-slate-600'}`}>Returns</button>
      </div>
      {mode === 'returns' ? (
        <div className="xl:col-span-12 min-h-0 overflow-y-auto">
          <ReturnsPanel storeId={storeId} />
        </div>
      ) : (
        <>
          <Card className="xl:col-span-8 min-h-0 flex flex-col">
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {screens.map((screen) => (
                <button
                  key={screen.id}
                  onClick={() => setActiveScreenId(screen.id)}
                  onDoubleClick={() => {
                    const next = window.prompt('Rename screen', screen.name);
                    if (!next?.trim()) return;
                    setScreens((prev) => prev.map((s) => (s.id === screen.id ? { ...s, name: next.trim() } : s)));
                  }}
                  className={`h-9 px-3 rounded-lg text-sm font-medium whitespace-nowrap border cursor-pointer ${activeScreenId === screen.id ? 'bg-primary-light border-primary/30 text-primary' : 'bg-white border-border text-slate-600 hover:bg-slate-50'}`}
                >
                  {screen.name}
                </button>
              ))}
              <Button variant="secondary" size="sm" onClick={() => {
                const id = `screen-${Date.now()}`;
                setScreens((prev) => [...prev, { id, name: `Screen ${prev.length + 1}`, product_ids: [] }]);
                setActiveScreenId(id);
              }}>+ Screen</Button>
            </div>
            <div className="mt-3 flex items-end gap-2">
              <div className="min-w-[240px]">
                <label className="text-sm font-medium text-slate-700">Add Product Button</label>
                <select value={selectedProductToAdd} onChange={(e) => setSelectedProductToAdd(e.target.value)} className="mt-1 h-10 w-full px-2 rounded-xl border border-border bg-white text-sm">
                  <option value="">Select product</option>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.sku} - {p.name}</option>)}
                </select>
              </div>
              <Button variant="secondary" onClick={() => {
                if (!selectedProductToAdd || !activeScreen) return;
                const pid = Number(selectedProductToAdd);
                if (activeScreen.product_ids.includes(pid)) return;
                setScreens((prev) => prev.map((s) => s.id === activeScreen.id ? { ...s, product_ids: [...s.product_ids, pid] } : s));
                setSelectedProductToAdd('');
              }} disabled={!selectedProductToAdd}>Add Button</Button>
              <Button variant={editMode ? 'primary' : 'ghost'} onClick={() => setEditMode((v) => !v)}>
                {editMode ? 'Done Editing' : 'Edit Buttons'}
              </Button>
            </div>
            <div className="mt-4 min-h-0 overflow-auto">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {quickProducts.map((product, index) => (
                  <div
                    key={product.id}
                    draggable={editMode}
                    onDragStart={() => editMode && setDragIndex(index)}
                    onDragOver={(e) => { if (editMode) e.preventDefault(); }}
                    onDrop={() => {
                      if (!editMode || dragIndex == null || !activeScreen) return;
                      const next = [...activeScreen.product_ids];
                      const [moved] = next.splice(dragIndex, 1);
                      next.splice(index, 0, moved);
                      setScreens((prev) => prev.map((s) => s.id === activeScreen.id ? { ...s, product_ids: next } : s));
                      setDragIndex(null);
                    }}
                    onDragEnd={() => setDragIndex(null)}
                    className={`rounded-xl border border-border bg-slate-50 p-2 ${editMode ? 'cursor-move' : ''}`}
                  >
                    <button onClick={() => addProduct(product.id)} disabled={busy || !currentSale} className="w-full text-left rounded-lg bg-white border border-border p-3 h-24 cursor-pointer hover:bg-slate-50">
                      <p className="text-sm font-semibold text-slate-900 line-clamp-2">{product.name}</p>
                      <p className="text-xs text-muted mt-1">{product.sku}</p>
                      <p className="text-sm font-medium mt-2">{formatMoney(product.price_cents ?? 0)}</p>
                    </button>
                    {editMode && activeScreen && (
                      <button
                        onClick={() => setScreens((prev) => prev.map((s) => s.id === activeScreen.id ? { ...s, product_ids: s.product_ids.filter((id) => id !== product.id) } : s))}
                        className="mt-2 text-xs text-slate-500 hover:text-slate-700 cursor-pointer"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Card>
          <div className="xl:col-span-4 min-h-0 flex flex-col gap-4">
            <Card className="min-h-0 flex-[3] flex flex-col">
              <div className="flex items-center justify-between">
                <div><CardTitle>Order Summary</CardTitle><CardDescription>{currentSale ? currentSale.document_number : 'Preparing sale...'}</CardDescription></div>
                {currentSale && <Badge variant="primary">{currentSale.status}</Badge>}
              </div>
              {error && <div className="mt-3 p-3 bg-red-50 text-red-700 text-sm rounded-xl">{error}</div>}
              <div className="mt-3 flex-1 min-h-0 overflow-auto border border-border rounded-xl">
                {lines.length === 0 ? <div className="p-4 text-sm text-muted">Cart is empty.</div> : (
                  <table className="w-full text-sm"><thead><tr className="border-b border-border text-left text-muted"><th className="px-3 py-2 font-medium">Item</th><th className="px-3 py-2 font-medium text-right">Qty</th><th className="px-3 py-2 font-medium text-right">Total</th></tr></thead><tbody>
                    {lines.map((line) => <tr key={line.id} className="border-b border-border/60"><td className="px-3 py-2">{productById.get(line.product_id)?.name ?? `Product #${line.product_id}`}</td><td className="px-3 py-2 text-right tabular-nums">{line.quantity}</td><td className="px-3 py-2 text-right tabular-nums">{formatMoney(line.line_total_cents)}</td></tr>)}
                  </tbody></table>
                )}
              </div>
              <div className="mt-3 space-y-1 text-sm"><div className="flex justify-between"><span className="text-muted">Items</span><span>{itemCount}</span></div><div className="flex justify-between text-lg font-semibold"><span>Total</span><span>{formatMoney(totalCents)}</span></div></div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Button onClick={postSale} disabled={busy || !currentSale || lines.length === 0}>Post Sale</Button>
                <Button variant="secondary" onClick={createNewSale} disabled={busy}>New Sale</Button>
              </div>
            </Card>

            <Card className="min-h-0 flex-[2] flex flex-col">
              <div className="flex items-center justify-between">
                <CardTitle>Payments</CardTitle>
                {paymentSummary?.payment_status && <Badge variant={isPaid ? 'success' : 'warning'}>{paymentSummary.payment_status}</Badge>}
              </div>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted">Due</span><span>{formatMoney(paymentSummary?.total_due_cents ?? totalCents)}</span></div>
                <div className="flex justify-between"><span className="text-muted">Paid</span><span>{formatMoney(paymentSummary?.total_paid_cents ?? 0)}</span></div>
                <div className="flex justify-between font-semibold"><span>Remaining</span><span>{formatMoney(remainingCents)}</span></div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2">
                <select value={paymentTender} onChange={(e) => setPaymentTender(e.target.value as TenderType)} className="h-10 px-2 rounded-xl border border-border bg-white text-sm">
                  {tenderOptions.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(e.target.value)}
                  placeholder="Amount (USD)"
                  className="h-10 px-3 rounded-xl border border-border text-sm"
                />
                {paymentTender !== 'CASH' && (
                  <input
                    value={paymentRef}
                    onChange={(e) => setPaymentRef(e.target.value)}
                    placeholder="Reference # (optional)"
                    className="h-10 px-3 rounded-xl border border-border text-sm"
                  />
                )}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Button onClick={applyPayment} disabled={paymentBusy || !currentSale || lines.length === 0}>
                  {paymentBusy ? 'Processing...' : 'Take Payment'}
                </Button>
                <Button variant="secondary" onClick={async () => { setCurrentSale(null); setLines([]); }} disabled={!isPaid}>
                  Complete Sale
                </Button>
              </div>
              {paymentSummary?.payments && paymentSummary.payments.length > 0 && (
                <div className="mt-3 border border-border rounded-xl max-h-28 overflow-auto">
                  {paymentSummary.payments.map((p) => (
                    <div key={p.id} className="px-3 py-2 text-xs flex items-center justify-between border-b border-border/60 last:border-b-0">
                      <span>{p.tender_type}</span>
                      <span>{formatMoney(p.amount_cents)}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="min-h-0 flex-[2] flex flex-col">
              <div className="flex items-center justify-between"><CardTitle>Tasks</CardTitle><Button variant="ghost" size="sm" onClick={loadTasks} disabled={tasksLoading}>Refresh</Button></div>
              <div className="mt-3 min-h-0 overflow-auto space-y-3">
                {tasksLoading ? <p className="text-sm text-muted">Loading tasks...</p> : (
                  <>
                    {announcements.length > 0 && (
                      <div>
                        <p className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Announcements</p>
                        <div className="space-y-2">
                          {announcements.map((a) => (
                            <div key={a.id} className="p-2 rounded-lg border border-border">
                              <p className="text-sm font-medium text-slate-900">{a.title}</p>
                              <p className="text-xs text-muted mt-0.5 line-clamp-1">{a.body}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {reminders.length > 0 && (
                      <div>
                        <p className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Reminders</p>
                        <div className="space-y-2">
                          {reminders.map((r) => (
                            <div key={r.id} className="p-2 rounded-lg border border-border">
                              <p className="text-sm font-medium text-slate-900">{r.title}</p>
                              <p className="text-xs text-muted mt-0.5 line-clamp-1">{r.body}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {commTasks.length > 0 && (
                      <div>
                        <p className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Assigned Tasks</p>
                        <div className="space-y-2">
                          {commTasks.map((ct) => (
                            <div key={ct.id} className="flex items-start justify-between gap-2 p-2 rounded-lg border border-border">
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-slate-900">{ct.title}</p>
                                {ct.description && <p className="text-xs text-muted mt-0.5 line-clamp-1">{ct.description}</p>}
                              </div>
                              <div className="flex gap-1 shrink-0">
                                <Button size="sm" onClick={() => completeCommTask(ct.id)}>Done</Button>
                                <Button size="sm" variant="secondary" onClick={() => deferCommTask(ct.id)}>Defer</Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {tasks.length > 0 && (
                      <div>
                        <p className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Document Tasks</p>
                        <table className="w-full text-sm"><thead><tr className="border-b border-border text-left text-muted"><th className="py-2 pr-2 font-medium">Type</th><th className="py-2 pr-2 font-medium">Document</th><th className="py-2 font-medium">Status</th></tr></thead><tbody>
                          {tasks.map((task) => <tr key={task.id} className="border-b border-border/60"><td className="py-2 pr-2">{task.document_type}</td><td className="py-2 pr-2 font-mono text-xs">{task.document_number}</td><td className="py-2"><Badge variant="warning">{task.status}</Badge></td></tr>)}
                        </tbody></table>
                      </div>
                    )}
                    {tasks.length === 0 && commTasks.length === 0 && announcements.length === 0 && reminders.length === 0 && (
                      <p className="text-sm text-muted">No pending tasks.</p>
                    )}
                  </>
                )}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
