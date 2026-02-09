import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney, formatDateTime } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Dialog } from '@/components/ui/Dialog';
import { Tabs } from '@/components/ui/Tabs';
import { Input, Select } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type Product = { id: number; sku: string; name: string; price_cents: number | null; is_active: boolean; store_id: number };
type Store = { id: number; name: string };

type SaleLine = { id: number; product_id: number; product_name?: string; quantity: number; unit_price_cents: number };
type Sale = { id: number; store_id: number; lines: SaleLine[] };

type Return = { id: number; sale_id: number; status: string; reason: string | null; restocking_fee_cents?: number; created_at: string; lines?: ReturnLine[] };
type ReturnLine = { id: number; return_id: number; sale_line_id: number; quantity: number; product_name?: string };

type Transfer = { id: number; from_store_id: number; to_store_id: number; from_store_name?: string; to_store_name?: string; status: string; reason: string | null; created_at: string; lines?: TransferLine[] };
type TransferLine = { id: number; transfer_id: number; product_id: number; product_name?: string; quantity: number };

type Count = { id: number; store_id: number; count_type: string; status: string; reason: string | null; created_at: string; lines?: CountLine[] };
type CountLine = { id: number; count_id: number; product_id: number; product_name?: string; expected_quantity: number; actual_quantity: number };

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'muted';

function statusVariant(status: string): BadgeVariant {
  switch (status.toUpperCase()) {
    case 'PENDING': return 'warning';
    case 'APPROVED': return 'success';
    case 'IN_TRANSIT': return 'primary';
    case 'RECEIVED':
    case 'COMPLETED':
    case 'POSTED': return 'success';
    case 'CANCELLED':
    case 'REJECTED': return 'danger';
    default: return 'default';
  }
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function WorkflowsPage({
  embedded = false,
  includeReturns = true,
}: {
  embedded?: boolean;
  includeReturns?: boolean;
}) {
  const { currentStoreId: storeId } = useStore();
  const [activeTab, setActiveTab] = useState(includeReturns ? 'Returns' : 'Transfers');

  return (
    <div className={`flex flex-col gap-6 ${embedded ? '' : 'max-w-6xl mx-auto'}`}>
      {!embedded && (
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Workflows</h1>
          <p className="text-sm text-muted mt-1">
            Manage returns, transfers, and inventory counts.
          </p>
        </div>
      )}

      <Tabs
        tabs={includeReturns ? ['Returns', 'Transfers', 'Counts'] : ['Transfers', 'Counts']}
        active={activeTab}
        onChange={setActiveTab}
      />

      {includeReturns && activeTab === 'Returns' && <ReturnsSection storeId={storeId} />}
      {activeTab === 'Transfers' && <TransfersSection storeId={storeId} />}
      {activeTab === 'Counts' && <CountsSection storeId={storeId} />}
    </div>
  );
}

/* ================================================================== */
/*  RETURNS SECTION                                                    */
/* ================================================================== */

function ReturnsSection({ storeId }: { storeId: number }) {
  // Sale lookup
  const [lookupSaleId, setLookupSaleId] = useState('');
  const [sale, setSale] = useState<Sale | null>(null);
  const [returnQtys, setReturnQtys] = useState<Record<number, number>>({});
  const [reason, setReason] = useState('');
  const [restockingFee, setRestockingFee] = useState('');

  // Returns list
  const [returns, setReturns] = useState<Return[]>([]);
  const [selectedReturn, setSelectedReturn] = useState<Return | null>(null);
  const [, setDetailLoading] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadReturns = useCallback(async () => {
    try {
      const res = await api.get<{ items?: Return[]; returns?: Return[] }>(`/api/returns?store_id=${storeId}`);
      setReturns(res.items ?? res.returns ?? []);
    } catch { setReturns([]); }
  }, [storeId]);

  useEffect(() => { loadReturns(); }, [loadReturns]);

  async function lookupSale() {
    if (!lookupSaleId.trim()) { setError('Enter a sale ID.'); return; }
    setError('');
    setSale(null);
    setReturnQtys({});
    try {
      const res = await api.get<Sale>(`/api/sales/${lookupSaleId}`);
      setSale(res);
      const qtyMap: Record<number, number> = {};
      (res.lines ?? []).forEach((l) => { qtyMap[l.id] = 0; });
      setReturnQtys(qtyMap);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Sale not found.');
    }
  }

  async function createReturn() {
    if (!sale) return;
    const linesToReturn = Object.entries(returnQtys).filter(([, qty]) => qty > 0);
    if (linesToReturn.length === 0) { setError('Set at least one return quantity.'); return; }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = { sale_id: sale.id };
      if (reason.trim()) body.reason = reason.trim();
      const fee = parseFloat(restockingFee);
      if (!Number.isNaN(fee) && fee > 0) body.restocking_fee_cents = Math.round(fee * 100);

      const res = await api.post<{ id: number }>('/api/returns', body);

      // Add lines
      for (const [lineId, qty] of linesToReturn) {
        await api.post(`/api/returns/${res.id}/lines`, {
          sale_line_id: Number(lineId),
          quantity: qty,
        });
      }

      setSuccess(`Return #${res.id} created with ${linesToReturn.length} line(s).`);
      setSale(null);
      setReturnQtys({});
      setReason('');
      setRestockingFee('');
      setLookupSaleId('');
      loadReturns();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to create return.');
    } finally {
      setBusy(false);
    }
  }

  async function viewReturn(r: Return) {
    setDetailLoading(true);
    try {
      const res = await api.get<Return>(`/api/returns/${r.id}`);
      setSelectedReturn(res);
    } catch {
      setSelectedReturn(r);
    } finally {
      setDetailLoading(false);
    }
  }

  async function performAction(id: number, action: string) {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/returns/${id}/${action}`);
      setSuccess(`Return #${id} ${action}d successfully.`);
      loadReturns();
      setSelectedReturn(null);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? `Failed to ${action} return.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>
      )}

      {/* Sale Lookup */}
      <Card>
        <CardTitle>Create Return</CardTitle>
        <CardDescription>Look up a sale to initiate a return.</CardDescription>

        <div className="flex flex-wrap gap-4 items-end mt-4">
          <Input
            label="Sale ID"
            type="number"
            min="1"
            value={lookupSaleId}
            onChange={(e) => setLookupSaleId(e.target.value)}
            placeholder="Enter sale ID"
            onKeyDown={(e) => e.key === 'Enter' && lookupSale()}
          />
          <Button variant="secondary" onClick={lookupSale}>Lookup Sale</Button>
        </div>

        {sale && (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-700 mb-2">Sale #{sale.id} Lines</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="py-2 pr-4 font-medium">Line</th>
                    <th className="py-2 pr-4 font-medium">Product</th>
                    <th className="py-2 pr-4 font-medium text-right">Qty Sold</th>
                    <th className="py-2 pr-4 font-medium text-right">Unit Price</th>
                    <th className="py-2 font-medium text-right">Return Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {(sale.lines ?? []).map((line) => (
                    <tr key={line.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 tabular-nums">{line.id}</td>
                      <td className="py-2 pr-4">{line.product_name ?? `Product #${line.product_id}`}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{line.quantity}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{formatMoney(line.unit_price_cents)}</td>
                      <td className="py-2 text-right">
                        <input
                          type="number"
                          min="0"
                          max={line.quantity}
                          value={returnQtys[line.id] ?? 0}
                          onChange={(e) => setReturnQtys((prev) => ({ ...prev, [line.id]: Number(e.target.value) }))}
                          className="w-20 h-9 px-2 rounded-lg border border-border text-sm text-right"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
              <Input
                label="Reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for return"
              />
              <Input
                label="Restocking Fee ($)"
                type="number"
                min="0"
                step="0.01"
                value={restockingFee}
                onChange={(e) => setRestockingFee(e.target.value)}
                placeholder="0.00"
              />
            </div>

            <div className="mt-4">
              <Button onClick={createReturn} disabled={busy}>
                {busy ? 'Creating...' : 'Create Return'}
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Returns List */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Returns</CardTitle>
          <CardDescription>All returns for this store.</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'id', header: 'ID', render: (r) => <span className="tabular-nums">{r.id}</span> },
              { key: 'sale_id', header: 'Sale ID', render: (r) => <span className="tabular-nums">{r.sale_id}</span> },
              { key: 'status', header: 'Status', render: (r) => <Badge variant={statusVariant(r.status)}>{r.status}</Badge> },
              { key: 'reason', header: 'Reason', render: (r) => <span className="text-muted">{r.reason ?? '-'}</span> },
              { key: 'created_at', header: 'Created', render: (r) => <span className="text-muted">{formatDateTime(r.created_at)}</span> },
              {
                key: 'actions', header: 'Actions', render: (r) => (
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => viewReturn(r)}>View</Button>
                    {r.status === 'PENDING' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => performAction(r.id, 'approve')}>Approve</Button>
                        <Button variant="ghost" size="sm" onClick={() => performAction(r.id, 'reject')}>Reject</Button>
                      </>
                    )}
                    {r.status === 'APPROVED' && (
                      <Button variant="ghost" size="sm" onClick={() => performAction(r.id, 'complete')}>Complete</Button>
                    )}
                  </div>
                ),
              },
            ]}
            data={returns}
            emptyMessage="No returns found."
          />
        </div>
        <div className="p-5 pt-3">
          <Button variant="secondary" size="sm" onClick={loadReturns}>Refresh</Button>
        </div>
      </Card>

      {/* Return Detail Dialog */}
      <Dialog open={!!selectedReturn} onClose={() => setSelectedReturn(null)} title={`Return #${selectedReturn?.id ?? ''}`} wide>
        {selectedReturn && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-muted">Sale ID:</span> {selectedReturn.sale_id}</div>
              <div><span className="text-muted">Status:</span> <Badge variant={statusVariant(selectedReturn.status)}>{selectedReturn.status}</Badge></div>
              <div><span className="text-muted">Reason:</span> {selectedReturn.reason ?? '-'}</div>
              <div><span className="text-muted">Created:</span> {formatDateTime(selectedReturn.created_at)}</div>
            </div>
            {selectedReturn.lines && selectedReturn.lines.length > 0 && (
              <div className="mt-2">
                <p className="text-sm font-medium mb-2">Lines</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted">
                        <th className="py-1.5 pr-3 font-medium">Product</th>
                        <th className="py-1.5 font-medium text-right">Quantity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedReturn.lines.map((l) => (
                        <tr key={l.id} className="border-b border-border/50">
                          <td className="py-1.5 pr-3">{l.product_name ?? `Line #${l.sale_line_id}`}</td>
                          <td className="py-1.5 text-right tabular-nums">{l.quantity}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Dialog>
    </div>
  );
}

/* ================================================================== */
/*  TRANSFERS SECTION                                                  */
/* ================================================================== */

function TransfersSection({ storeId }: { storeId: number }) {
  const [stores, setStores] = useState<Store[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  // Create form
  const [fromStoreId, setFromStoreId] = useState(String(storeId));
  const [toStoreId, setToStoreId] = useState('');
  const [transferReason, setTransferReason] = useState('');
  const [transferLines, setTransferLines] = useState<{ product_id: string; quantity: string }[]>([
    { product_id: '', quantity: '1' },
  ]);

  // List
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [selectedTransfer, setSelectedTransfer] = useState<Transfer | null>(null);
  const [, setDetailLoading] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    api
      .get<{ stores?: Store[]; items?: Store[] } | Store[]>('/api/stores')
      .then((d) => setStores(Array.isArray(d) ? d : (d.stores ?? d.items ?? [])))
      .catch(() => {});
    api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`).then((d) => setProducts(d.items ?? [])).catch(() => {});
  }, [storeId]);

  const loadTransfers = useCallback(async () => {
    try {
      const res = await api.get<{ items?: Transfer[]; transfers?: Transfer[] }>(`/api/transfers?store_id=${storeId}`);
      setTransfers(res.items ?? res.transfers ?? []);
    } catch { setTransfers([]); }
  }, [storeId]);

  useEffect(() => { loadTransfers(); }, [loadTransfers]);

  function addTransferLine() {
    setTransferLines((prev) => [...prev, { product_id: '', quantity: '1' }]);
  }

  function removeTransferLine(idx: number) {
    setTransferLines((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateTransferLine(idx: number, field: 'product_id' | 'quantity', value: string) {
    setTransferLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [field]: value } : l)));
  }

  async function createTransfer() {
    if (!fromStoreId || !toStoreId) { setError('Select both from and to stores.'); return; }
    if (fromStoreId === toStoreId) { setError('From and to stores must be different.'); return; }
    const validLines = transferLines.filter((l) => l.product_id && Number(l.quantity) > 0);
    if (validLines.length === 0) { setError('Add at least one product with a positive quantity.'); return; }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = {
        from_store_id: Number(fromStoreId),
        to_store_id: Number(toStoreId),
      };
      if (transferReason.trim()) body.reason = transferReason.trim();

      const res = await api.post<{ id: number }>('/api/transfers', body);

      for (const line of validLines) {
        await api.post(`/api/transfers/${res.id}/lines`, {
          product_id: Number(line.product_id),
          quantity: Number(line.quantity),
        });
      }

      setSuccess(`Transfer #${res.id} created with ${validLines.length} line(s).`);
      setToStoreId('');
      setTransferReason('');
      setTransferLines([{ product_id: '', quantity: '1' }]);
      loadTransfers();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to create transfer.');
    } finally {
      setBusy(false);
    }
  }

  async function viewTransfer(t: Transfer) {
    setDetailLoading(true);
    try {
      const res = await api.get<Transfer>(`/api/transfers/${t.id}`);
      setSelectedTransfer(res);
    } catch {
      setSelectedTransfer(t);
    } finally {
      setDetailLoading(false);
    }
  }

  async function performAction(id: number, action: string) {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/transfers/${id}/${action}`);
      setSuccess(`Transfer #${id} ${action}${action.endsWith('e') ? 'd' : 'ed'} successfully.`);
      loadTransfers();
      setSelectedTransfer(null);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? `Failed to ${action} transfer.`);
    } finally {
      setBusy(false);
    }
  }

  const storeName = (id: number) => stores.find((s) => s.id === id)?.name ?? `Store #${id}`;

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>
      )}

      {/* Create Transfer */}
      <Card>
        <CardTitle>Create Transfer</CardTitle>
        <CardDescription>Transfer inventory between stores.</CardDescription>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          <Select
            label="From Store"
            value={fromStoreId}
            onChange={(e) => setFromStoreId(e.target.value)}
            options={[
              { value: '', label: '-- Select Store --' },
              ...stores.map((s) => ({ value: String(s.id), label: s.name })),
            ]}
          />
          <Select
            label="To Store"
            value={toStoreId}
            onChange={(e) => setToStoreId(e.target.value)}
            options={[
              { value: '', label: '-- Select Store --' },
              ...stores.map((s) => ({ value: String(s.id), label: s.name })),
            ]}
          />
          <Input
            label="Reason"
            value={transferReason}
            onChange={(e) => setTransferReason(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="mt-4">
          <p className="text-sm font-medium text-slate-700 mb-2">Products</p>
          <div className="flex flex-col gap-2">
            {transferLines.map((line, idx) => (
              <div key={idx} className="flex gap-2 items-end">
                <div className="flex-1">
                  <Select
                    label={idx === 0 ? 'Product' : undefined}
                    value={line.product_id}
                    onChange={(e) => updateTransferLine(idx, 'product_id', e.target.value)}
                    options={[
                      { value: '', label: '-- Select Product --' },
                      ...products.map((p) => ({ value: String(p.id), label: `${p.sku} - ${p.name}` })),
                    ]}
                  />
                </div>
                <div className="w-24">
                  <Input
                    label={idx === 0 ? 'Qty' : undefined}
                    type="number"
                    min="1"
                    value={line.quantity}
                    onChange={(e) => updateTransferLine(idx, 'quantity', e.target.value)}
                  />
                </div>
                {transferLines.length > 1 && (
                  <Button variant="ghost" size="sm" onClick={() => removeTransferLine(idx)}>Remove</Button>
                )}
              </div>
            ))}
          </div>
          <Button variant="ghost" size="sm" onClick={addTransferLine} className="mt-2">+ Add Product</Button>
        </div>

        <div className="mt-4">
          <Button onClick={createTransfer} disabled={busy}>
            {busy ? 'Creating...' : 'Create Transfer'}
          </Button>
        </div>
      </Card>

      {/* Transfers List */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Transfers</CardTitle>
          <CardDescription>All transfers for this store.</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'id', header: 'ID', render: (t) => <span className="tabular-nums">{t.id}</span> },
              { key: 'from', header: 'From', render: (t) => t.from_store_name ?? storeName(t.from_store_id) },
              { key: 'to', header: 'To', render: (t) => t.to_store_name ?? storeName(t.to_store_id) },
              { key: 'status', header: 'Status', render: (t) => <Badge variant={statusVariant(t.status)}>{t.status}</Badge> },
              { key: 'created_at', header: 'Created', render: (t) => <span className="text-muted">{formatDateTime(t.created_at)}</span> },
              {
                key: 'actions', header: 'Actions', render: (t) => (
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => viewTransfer(t)}>View</Button>
                    {t.status === 'PENDING' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => performAction(t.id, 'approve')}>Approve</Button>
                        <Button variant="ghost" size="sm" onClick={() => performAction(t.id, 'cancel')}>Cancel</Button>
                      </>
                    )}
                    {t.status === 'APPROVED' && (
                      <Button variant="ghost" size="sm" onClick={() => performAction(t.id, 'ship')}>Ship</Button>
                    )}
                    {t.status === 'IN_TRANSIT' && (
                      <Button variant="ghost" size="sm" onClick={() => performAction(t.id, 'receive')}>Receive</Button>
                    )}
                  </div>
                ),
              },
            ]}
            data={transfers}
            emptyMessage="No transfers found."
          />
        </div>
        <div className="p-5 pt-3">
          <Button variant="secondary" size="sm" onClick={loadTransfers}>Refresh</Button>
        </div>
      </Card>

      {/* Transfer Detail Dialog */}
      <Dialog open={!!selectedTransfer} onClose={() => setSelectedTransfer(null)} title={`Transfer #${selectedTransfer?.id ?? ''}`} wide>
        {selectedTransfer && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-muted">From:</span> {selectedTransfer.from_store_name ?? storeName(selectedTransfer.from_store_id)}</div>
              <div><span className="text-muted">To:</span> {selectedTransfer.to_store_name ?? storeName(selectedTransfer.to_store_id)}</div>
              <div><span className="text-muted">Status:</span> <Badge variant={statusVariant(selectedTransfer.status)}>{selectedTransfer.status}</Badge></div>
              <div><span className="text-muted">Reason:</span> {selectedTransfer.reason ?? '-'}</div>
              <div><span className="text-muted">Created:</span> {formatDateTime(selectedTransfer.created_at)}</div>
            </div>
            {selectedTransfer.lines && selectedTransfer.lines.length > 0 && (
              <div className="mt-2">
                <p className="text-sm font-medium mb-2">Lines</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted">
                        <th className="py-1.5 pr-3 font-medium">Product</th>
                        <th className="py-1.5 font-medium text-right">Quantity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTransfer.lines.map((l) => (
                        <tr key={l.id} className="border-b border-border/50">
                          <td className="py-1.5 pr-3">{l.product_name ?? `Product #${l.product_id}`}</td>
                          <td className="py-1.5 text-right tabular-nums">{l.quantity}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Dialog>
    </div>
  );
}

/* ================================================================== */
/*  COUNTS SECTION                                                     */
/* ================================================================== */

function CountsSection({ storeId }: { storeId: number }) {
  const [products, setProducts] = useState<Product[]>([]);

  // Create form
  const [countType, setCountType] = useState('CYCLE');
  const [countReason, setCountReason] = useState('');

  // Active count
  const [activeCountId, setActiveCountId] = useState<number | null>(null);
  const [countProductId, setCountProductId] = useState('');
  const [actualQty, setActualQty] = useState('');
  const [countedItems, setCountedItems] = useState<CountLine[]>([]);

  // List
  const [counts, setCounts] = useState<Count[]>([]);
  const [selectedCount, setSelectedCount] = useState<Count | null>(null);
  const [, setDetailLoading] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`).then((d) => setProducts(d.items ?? [])).catch(() => {});
  }, [storeId]);

  const loadCounts = useCallback(async () => {
    try {
      const res = await api.get<{ items?: Count[]; counts?: Count[] }>(`/api/counts?store_id=${storeId}`);
      setCounts(res.items ?? res.counts ?? []);
    } catch { setCounts([]); }
  }, [storeId]);

  useEffect(() => { loadCounts(); }, [loadCounts]);

  async function startCount() {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = {
        store_id: storeId,
        count_type: countType,
      };
      if (countReason.trim()) body.reason = countReason.trim();

      const res = await api.post<{ id: number }>('/api/counts', body);
      setActiveCountId(res.id);
      setCountedItems([]);
      setSuccess(`Count #${res.id} started. Add items below.`);
      setCountReason('');
      loadCounts();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to start count.');
    } finally {
      setBusy(false);
    }
  }

  async function addCountLine() {
    if (!activeCountId) return;
    if (!countProductId) { setError('Select a product.'); return; }
    const qty = Number(actualQty);
    if (Number.isNaN(qty) || qty < 0) { setError('Enter a valid actual quantity.'); return; }

    setBusy(true);
    setError('');
    try {
      const res = await api.post<CountLine>(`/api/counts/${activeCountId}/lines`, {
        product_id: Number(countProductId),
        actual_quantity: qty,
      });
      setCountedItems((prev) => [...prev, res]);
      setCountProductId('');
      setActualQty('');
      setSuccess('Item added.');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to add count line.');
    } finally {
      setBusy(false);
    }
  }

  async function viewCount(c: Count) {
    setDetailLoading(true);
    try {
      const res = await api.get<Count>(`/api/counts/${c.id}`);
      setSelectedCount(res);
    } catch {
      setSelectedCount(c);
    } finally {
      setDetailLoading(false);
    }
  }

  async function performAction(id: number, action: string) {
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/counts/${id}/${action}`);
      setSuccess(`Count #${id} ${action}${action.endsWith('e') ? 'd' : 'ed'} successfully.`);
      loadCounts();
      setSelectedCount(null);
      if (id === activeCountId && (action === 'cancel' || action === 'post')) {
        setActiveCountId(null);
        setCountedItems([]);
      }
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? `Failed to ${action} count.`);
    } finally {
      setBusy(false);
    }
  }

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `Product #${id}`;

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>
      )}

      {/* Start Count */}
      {!activeCountId && (
        <Card>
          <CardTitle>Start New Count</CardTitle>
          <CardDescription>Begin a cycle or full inventory count.</CardDescription>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
            <Select
              label="Count Type"
              value={countType}
              onChange={(e) => setCountType(e.target.value)}
              options={[
                { value: 'CYCLE', label: 'Cycle Count' },
                { value: 'FULL', label: 'Full Count' },
              ]}
            />
            <Input
              label="Reason"
              value={countReason}
              onChange={(e) => setCountReason(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="mt-4">
            <Button onClick={startCount} disabled={busy}>
              {busy ? 'Starting...' : 'Start Count'}
            </Button>
          </div>
        </Card>
      )}

      {/* Active Count */}
      {activeCountId && (
        <Card>
          <CardTitle>Count #{activeCountId} - Add Items</CardTitle>

          <div className="flex flex-wrap gap-4 items-end mt-4">
            <div className="flex-1 min-w-[200px]">
              <Select
                label="Product"
                value={countProductId}
                onChange={(e) => setCountProductId(e.target.value)}
                options={[
                  { value: '', label: '-- Select Product --' },
                  ...products.map((p) => ({ value: String(p.id), label: `${p.sku} - ${p.name}` })),
                ]}
              />
            </div>
            <div className="w-32">
              <Input
                label="Actual Qty"
                type="number"
                min="0"
                value={actualQty}
                onChange={(e) => setActualQty(e.target.value)}
                placeholder="0"
              />
            </div>
            <Button onClick={addCountLine} disabled={busy}>Add Item</Button>
          </div>

          {/* Counted Items */}
          {countedItems.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="py-2 pr-4 font-medium">Product</th>
                    <th className="py-2 pr-4 font-medium text-right">Expected</th>
                    <th className="py-2 pr-4 font-medium text-right">Actual</th>
                    <th className="py-2 font-medium text-right">Variance</th>
                  </tr>
                </thead>
                <tbody>
                  {countedItems.map((item, i) => {
                    const variance = item.actual_quantity - item.expected_quantity;
                    return (
                      <tr key={i} className="border-b border-border/50">
                        <td className="py-2 pr-4">{item.product_name ?? productName(item.product_id)}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{item.expected_quantity}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{item.actual_quantity}</td>
                        <td className={`py-2 text-right tabular-nums font-medium ${variance > 0 ? 'text-emerald-600' : variance < 0 ? 'text-red-600' : 'text-slate-500'}`}>
                          {variance > 0 ? '+' : ''}{variance}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex gap-2 mt-4">
            <Button variant="secondary" onClick={() => performAction(activeCountId, 'approve')} disabled={busy}>
              Approve
            </Button>
            <Button variant="warning" onClick={() => performAction(activeCountId, 'post')} disabled={busy}>
              Post
            </Button>
            <Button variant="ghost" onClick={() => performAction(activeCountId, 'cancel')} disabled={busy}>
              Cancel Count
            </Button>
            <Button variant="ghost" onClick={() => { setActiveCountId(null); setCountedItems([]); }}>
              Close
            </Button>
          </div>
        </Card>
      )}

      {/* Counts List */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Counts</CardTitle>
          <CardDescription>All inventory counts for this store.</CardDescription>
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              { key: 'id', header: 'ID', render: (c) => <span className="tabular-nums">{c.id}</span> },
              { key: 'count_type', header: 'Type', render: (c) => <Badge>{c.count_type}</Badge> },
              { key: 'status', header: 'Status', render: (c) => <Badge variant={statusVariant(c.status)}>{c.status}</Badge> },
              { key: 'reason', header: 'Reason', render: (c) => <span className="text-muted">{c.reason ?? '-'}</span> },
              { key: 'created_at', header: 'Created', render: (c) => <span className="text-muted">{formatDateTime(c.created_at)}</span> },
              {
                key: 'actions', header: 'Actions', render: (c) => (
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => viewCount(c)}>View</Button>
                    {c.status === 'PENDING' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => { setActiveCountId(c.id); setCountedItems([]); }}>Add Items</Button>
                        <Button variant="ghost" size="sm" onClick={() => performAction(c.id, 'approve')}>Approve</Button>
                        <Button variant="ghost" size="sm" onClick={() => performAction(c.id, 'cancel')}>Cancel</Button>
                      </>
                    )}
                    {c.status === 'APPROVED' && (
                      <Button variant="ghost" size="sm" onClick={() => performAction(c.id, 'post')}>Post</Button>
                    )}
                  </div>
                ),
              },
            ]}
            data={counts}
            emptyMessage="No counts found."
          />
        </div>
        <div className="p-5 pt-3">
          <Button variant="secondary" size="sm" onClick={loadCounts}>Refresh</Button>
        </div>
      </Card>

      {/* Count Detail Dialog */}
      <Dialog open={!!selectedCount} onClose={() => setSelectedCount(null)} title={`Count #${selectedCount?.id ?? ''}`} wide>
        {selectedCount && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-muted">Type:</span> <Badge>{selectedCount.count_type}</Badge></div>
              <div><span className="text-muted">Status:</span> <Badge variant={statusVariant(selectedCount.status)}>{selectedCount.status}</Badge></div>
              <div><span className="text-muted">Reason:</span> {selectedCount.reason ?? '-'}</div>
              <div><span className="text-muted">Created:</span> {formatDateTime(selectedCount.created_at)}</div>
            </div>
            {selectedCount.lines && selectedCount.lines.length > 0 && (
              <div className="mt-2">
                <p className="text-sm font-medium mb-2">Lines</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted">
                        <th className="py-1.5 pr-3 font-medium">Product</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Expected</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Actual</th>
                        <th className="py-1.5 font-medium text-right">Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedCount.lines.map((l) => {
                        const variance = l.actual_quantity - l.expected_quantity;
                        return (
                          <tr key={l.id} className="border-b border-border/50">
                            <td className="py-1.5 pr-3">{l.product_name ?? productName(l.product_id)}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{l.expected_quantity}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{l.actual_quantity}</td>
                            <td className={`py-1.5 text-right tabular-nums font-medium ${variance > 0 ? 'text-emerald-600' : variance < 0 ? 'text-red-600' : 'text-slate-500'}`}>
                              {variance > 0 ? '+' : ''}{variance}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Dialog>
    </div>
  );
}
