import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { formatDateTime } from '@/lib/format';

type SaleLine = { id: number; product_id: number; product_name?: string; quantity: number; unit_price_cents: number };
type Sale = { id: number; store_id: number; lines: SaleLine[] };
type Return = { id: number; sale_id: number; status: string; reason: string | null; created_at: string };

function statusVariant(status: string) {
  switch (status.toUpperCase()) {
    case 'PENDING': return 'warning' as const;
    case 'APPROVED': return 'success' as const;
    case 'COMPLETED':
    case 'POSTED': return 'success' as const;
    case 'REJECTED': return 'danger' as const;
    default: return 'default' as const;
  }
}

export function ReturnsPanel({ storeId }: { storeId: number }) {
  const [lookupSaleId, setLookupSaleId] = useState('');
  const [sale, setSale] = useState<Sale | null>(null);
  const [returnQtys, setReturnQtys] = useState<Record<number, number>>({});
  const [reason, setReason] = useState('');
  const [returns, setReturns] = useState<Return[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function loadReturns() {
    try {
      const res = await api.get<{ items?: Return[]; returns?: Return[] }>(`/api/returns?store_id=${storeId}`);
      setReturns(res.items ?? res.returns ?? []);
    } catch {
      setReturns([]);
    }
  }

  useEffect(() => {
    loadReturns();
  }, [storeId]);

  async function lookupSale() {
    if (!lookupSaleId.trim()) return;
    setError('');
    try {
      const res = await api.get<Sale>(`/api/sales/${lookupSaleId.trim()}`);
      setSale(res);
      const qtyMap: Record<number, number> = {};
      (res.lines ?? []).forEach((l) => { qtyMap[l.id] = 0; });
      setReturnQtys(qtyMap);
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Sale not found.');
      setSale(null);
    }
  }

  async function createReturn() {
    if (!sale) return;
    const linesToReturn = Object.entries(returnQtys).filter(([, qty]) => qty > 0);
    if (linesToReturn.length === 0) {
      setError('Set at least one return quantity.');
      return;
    }
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = { sale_id: sale.id };
      if (reason.trim()) body.reason = reason.trim();
      const res = await api.post<{ id: number }>('/api/returns', body);
      for (const [lineId, qty] of linesToReturn) {
        await api.post(`/api/returns/${res.id}/lines`, { sale_line_id: Number(lineId), quantity: qty });
      }
      setSuccess(`Return #${res.id} created.`);
      setSale(null);
      setReturnQtys({});
      setLookupSaleId('');
      setReason('');
      loadReturns();
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to create return.');
    } finally {
      setBusy(false);
    }
  }

  async function act(id: number, action: 'approve' | 'reject' | 'complete') {
    setBusy(true);
    setError('');
    try {
      await api.post(`/api/returns/${id}/${action}`);
      setSuccess(`Return #${id} ${action}d.`);
      loadReturns();
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed action.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">{success}</div>}

      <Card>
        <CardTitle>Create Return</CardTitle>
        <CardDescription>Look up a sale and create return lines.</CardDescription>
        <div className="flex flex-wrap gap-3 items-end mt-4">
          <Input label="Sale ID" value={lookupSaleId} onChange={(e) => setLookupSaleId(e.target.value)} />
          <Button variant="secondary" onClick={lookupSale}>Lookup</Button>
        </div>

        {sale && (
          <div className="mt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="py-2 pr-4 font-medium">Line</th>
                    <th className="py-2 pr-4 font-medium">Product</th>
                    <th className="py-2 pr-4 font-medium text-right">Qty Sold</th>
                    <th className="py-2 font-medium text-right">Return Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {(sale.lines ?? []).map((line) => (
                    <tr key={line.id} className="border-b border-border/50">
                      <td className="py-2 pr-4">{line.id}</td>
                      <td className="py-2 pr-4">{line.product_name ?? `Product #${line.product_id}`}</td>
                      <td className="py-2 pr-4 text-right">{line.quantity}</td>
                      <td className="py-2 text-right">
                        <input type="number" min="0" max={line.quantity} value={returnQtys[line.id] ?? 0} onChange={(e) => setReturnQtys((prev) => ({ ...prev, [line.id]: Number(e.target.value) }))} className="w-20 h-9 px-2 rounded-lg border border-border text-sm text-right" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 max-w-md">
              <Input label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Optional" />
            </div>
            <div className="mt-4">
              <Button onClick={createReturn} disabled={busy}>{busy ? 'Creating...' : 'Create Return'}</Button>
            </div>
          </div>
        )}
      </Card>

      <Card padding={false}>
        <div className="p-5 pb-0"><CardTitle>Returns</CardTitle></div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="py-2 px-5 font-medium">ID</th>
                <th className="py-2 px-3 font-medium">Sale</th>
                <th className="py-2 px-3 font-medium">Status</th>
                <th className="py-2 px-3 font-medium">Created</th>
                <th className="py-2 px-5 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id} className="border-b border-border/50">
                  <td className="py-2 px-5">{r.id}</td>
                  <td className="py-2 px-3">{r.sale_id}</td>
                  <td className="py-2 px-3"><Badge variant={statusVariant(r.status)}>{r.status}</Badge></td>
                  <td className="py-2 px-3">{formatDateTime(r.created_at)}</td>
                  <td className="py-2 px-5 text-right">
                    <div className="flex justify-end gap-1">
                      {r.status === 'PENDING' && <><Button variant="ghost" size="sm" onClick={() => act(r.id, 'approve')} disabled={busy}>Approve</Button><Button variant="ghost" size="sm" onClick={() => act(r.id, 'reject')} disabled={busy}>Reject</Button></>}
                      {r.status === 'APPROVED' && <Button variant="ghost" size="sm" onClick={() => act(r.id, 'complete')} disabled={busy}>Complete</Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
