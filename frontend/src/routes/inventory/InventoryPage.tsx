import { useCallback, useEffect, useState } from 'react';

import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney, formatDateTime } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Tabs } from '@/components/ui/Tabs';
import { Input, Select } from '@/components/ui/Input';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type Product = {
  id: number;
  sku: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
  store_id: number;
};

type Vendor = { id: number; name: string; code: string | null };

type InventorySummary = {
  store_id: number;
  product_id: number;
  quantity_on_hand: number;
  weighted_average_cost_cents: number | null;
  recent_unit_cost_cents: number | null;
};

type LedgerEntry = {
  id: number;
  transaction_type: string;
  quantity_delta: number;
  unit_cost_cents: number;
  occurred_at: string;
  note: string | null;
  product_id?: number;
};

type PendingDocument = {
  id: number;
  document_type: string;
  document_number: string;
  status: string;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function datetimeLocalToUtcIso(value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/* ------------------------------------------------------------------ */
/*  Identifier lookup helper                                           */
/* ------------------------------------------------------------------ */

async function lookupIdentifier(
  value: string,
): Promise<{ product?: Product; products?: Product[]; ambiguous?: boolean }> {
  const token = api.getToken();
  const res = await fetch(`/api/identifiers/lookup/${encodeURIComponent(value)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Lookup failed: ${res.status}`);
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export function InventoryPage() {

  const { currentStoreId: storeId } = useStore();
  const [activeTab, setActiveTab] = useState('Receive');

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Inventory</h1>
        <p className="text-sm text-muted mt-1">
          Receive, adjust, and manage inventory for your store.
        </p>
      </div>

      <Tabs
        tabs={['Receive', 'Adjust', 'Products', 'Ledger', 'Lifecycle']}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'Receive' && <ReceiveSection storeId={storeId} />}
      {activeTab === 'Adjust' && <AdjustSection storeId={storeId} />}
      {activeTab === 'Products' && <ProductsSection storeId={storeId} />}
      {activeTab === 'Ledger' && <LedgerSection storeId={storeId} />}
      {activeTab === 'Lifecycle' && <LifecycleSection storeId={storeId} />}
    </div>
  );
}

/* ================================================================== */
/*  RECEIVE SECTION                                                    */
/* ================================================================== */

function ReceiveSection({ storeId }: { storeId: number }) {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [receiveTypes, setReceiveTypes] = useState<string[]>([]);

  const [vendorId, setVendorId] = useState('');
  const [receiveType, setReceiveType] = useState('');
  const [headerNote, setHeaderNote] = useState('');
  const [headerOccurredAt, setHeaderOccurredAt] = useState('');

  const [receiveId, setReceiveId] = useState<number | null>(null);
  const [lines, setLines] = useState<
    { product_id: number; quantity: number; unit_cost_cents: number; note: string }[]
  >([]);

  // Line form
  const [scanValue, setScanValue] = useState('');
  const [selectedProductId, setSelectedProductId] = useState('');
  const [lineQty, setLineQty] = useState('1');
  const [lineUnitCost, setLineUnitCost] = useState('');
  const [lineNote, setLineNote] = useState('');

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [lookupResults, setLookupResults] = useState<Product[] | null>(null);

  useEffect(() => {
    api.get<{ items: Vendor[] }>('/api/vendors').then((d) => setVendors(d.items ?? [])).catch(() => {});
    api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`).then((d) => setProducts(d.items ?? [])).catch(() => {});
    api.get<{ types: string[] }>('/api/receives/types').then((d) => {
      setReceiveTypes(d.types ?? []);
      if (d.types?.length) setReceiveType(d.types[0]);
    }).catch(() => {});
  }, [storeId]);

  async function handleScan() {
    if (!scanValue.trim()) return;
    setError('');
    setLookupResults(null);
    try {
      const result = await lookupIdentifier(scanValue.trim());
      if (result.product) {
        setSelectedProductId(String(result.product.id));
        setScanValue('');
      } else if (result.ambiguous && result.products?.length) {
        setLookupResults(result.products);
      } else {
        setError('No product found for that identifier.');
      }
    } catch {
      setError('Lookup failed.');
    }
  }

  async function createReceive() {
    if (!vendorId) { setError('Select a vendor.'); return; }
    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        store_id: storeId,
        vendor_id: Number(vendorId),
        receive_type: receiveType,
      };
      if (headerNote.trim()) body.note = headerNote.trim();
      const occ = datetimeLocalToUtcIso(headerOccurredAt);
      if (occ) body.occurred_at = occ;

      const res = await api.post<{ id: number }>('/api/receives', body);
      setReceiveId(res.id);
      setSuccess(`Receive #${res.id} created. Add lines below.`);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to create receive.');
    } finally {
      setBusy(false);
    }
  }

  async function addLine() {
    if (!receiveId) return;
    if (!selectedProductId) { setError('Select a product.'); return; }
    const qty = Number(lineQty);
    const costDollars = parseFloat(lineUnitCost);
    if (!qty || qty <= 0) { setError('Quantity must be positive.'); return; }
    if (Number.isNaN(costDollars) || costDollars < 0) { setError('Enter a valid unit cost.'); return; }

    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        product_id: Number(selectedProductId),
        quantity: qty,
        unit_cost_cents: Math.round(costDollars * 100),
      };
      if (lineNote.trim()) body.note = lineNote.trim();

      await api.post(`/api/receives/${receiveId}/lines`, body);
      setLines((prev) => [
        ...prev,
        {
          product_id: Number(selectedProductId),
          quantity: qty,
          unit_cost_cents: Math.round(costDollars * 100),
          note: lineNote.trim(),
        },
      ]);
      setSelectedProductId('');
      setLineQty('1');
      setLineUnitCost('');
      setLineNote('');
      setScanValue('');
      setSuccess('Line added.');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to add line.');
    } finally {
      setBusy(false);
    }
  }

  async function approveReceive() {
    if (!receiveId) return;
    setBusy(true);
    setError('');
    try {
      await api.post(`/api/receives/${receiveId}/approve`);
      setSuccess(`Receive #${receiveId} approved.`);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Approval failed.');
    } finally {
      setBusy(false);
    }
  }

  async function postReceive() {
    if (!receiveId) return;
    setBusy(true);
    setError('');
    try {
      await api.post(`/api/receives/${receiveId}/post`);
      setSuccess(`Receive #${receiveId} posted. Inventory updated.`);
      resetForm();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Post failed.');
    } finally {
      setBusy(false);
    }
  }

  function resetForm() {
    setReceiveId(null);
    setLines([]);
    setVendorId('');
    setHeaderNote('');
    setHeaderOccurredAt('');
    setSelectedProductId('');
    setLineQty('1');
    setLineUnitCost('');
    setLineNote('');
    setScanValue('');
    setLookupResults(null);
  }

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`;

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      {/* Header */}
      {!receiveId && (
        <Card>
          <CardTitle>New Receive</CardTitle>
          <CardDescription>Create a new inventory receive document.</CardDescription>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
            <Select
              label="Vendor"
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              options={[
                { value: '', label: '-- Select Vendor --' },
                ...vendors.map((v) => ({ value: String(v.id), label: v.name })),
              ]}
            />
            <Select
              label="Receive Type"
              value={receiveType}
              onChange={(e) => setReceiveType(e.target.value)}
              options={receiveTypes.map((t) => ({ value: t, label: t }))}
            />
            <Input
              label="Occurred At"
              type="datetime-local"
              value={headerOccurredAt}
              onChange={(e) => setHeaderOccurredAt(e.target.value)}
            />
            <Input
              label="Note"
              value={headerNote}
              onChange={(e) => setHeaderNote(e.target.value)}
              placeholder="Optional note"
            />
          </div>

          <div className="mt-4">
            <Button onClick={createReceive} disabled={busy}>
              Create Receive
            </Button>
          </div>
        </Card>
      )}

      {/* Line entry */}
      {receiveId && (
        <Card>
          <CardTitle>Receive #{receiveId} - Add Lines</CardTitle>

          {/* Scan / Search */}
          <div className="flex gap-2 mt-4">
            <div className="flex-1">
              <Input
                label="Scan / Search Identifier"
                value={scanValue}
                onChange={(e) => setScanValue(e.target.value)}
                placeholder="Scan barcode or type identifier"
                onKeyDown={(e) => e.key === 'Enter' && handleScan()}
              />
            </div>
            <div className="flex items-end">
              <Button variant="secondary" onClick={handleScan}>
                Lookup
              </Button>
            </div>
          </div>

          {lookupResults && (
            <div className="mt-2 p-3 rounded-xl bg-amber-50 border border-amber-200">
              <p className="text-sm font-medium text-amber-800 mb-2">
                Ambiguous result - select a product:
              </p>
              <div className="flex flex-wrap gap-2">
                {lookupResults.map((p) => (
                  <Button
                    key={p.id}
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedProductId(String(p.id));
                      setLookupResults(null);
                      setScanValue('');
                    }}
                  >
                    {p.sku} - {p.name}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
            <Select
              label="Product"
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              options={[
                { value: '', label: '-- Select Product --' },
                ...products.map((p) => ({
                  value: String(p.id),
                  label: `${p.sku} - ${p.name}`,
                })),
              ]}
            />
            <Input
              label="Quantity"
              type="number"
              min="1"
              value={lineQty}
              onChange={(e) => setLineQty(e.target.value)}
            />
            <Input
              label="Unit Cost ($)"
              type="number"
              min="0"
              step="0.01"
              value={lineUnitCost}
              onChange={(e) => setLineUnitCost(e.target.value)}
              placeholder="0.00"
            />
            <Input
              label="Line Note"
              value={lineNote}
              onChange={(e) => setLineNote(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="flex gap-2 mt-4">
            <Button onClick={addLine} disabled={busy}>
              Add Line
            </Button>
            <Button variant="secondary" onClick={approveReceive} disabled={busy}>
              Approve
            </Button>
            <Button variant="warning" onClick={postReceive} disabled={busy}>
              Post
            </Button>
            <Button variant="ghost" onClick={resetForm}>
              Reset
            </Button>
          </div>

          {/* Lines table */}
          {lines.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="py-2 pr-4 font-medium">Product</th>
                    <th className="py-2 pr-4 font-medium">Qty</th>
                    <th className="py-2 pr-4 font-medium">Unit Cost</th>
                    <th className="py-2 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, i) => (
                    <tr key={i} className="border-b border-border/50">
                      <td className="py-2 pr-4">{productName(line.product_id)}</td>
                      <td className="py-2 pr-4">{line.quantity}</td>
                      <td className="py-2 pr-4">{formatMoney(line.unit_cost_cents)}</td>
                      <td className="py-2 text-muted">{line.note || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

/* ================================================================== */
/*  ADJUST SECTION                                                     */
/* ================================================================== */

function AdjustSection({ storeId }: { storeId: number }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [scanValue, setScanValue] = useState('');
  const [quantityDelta, setQuantityDelta] = useState('');
  const [occurredAt, setOccurredAt] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [lookupResults, setLookupResults] = useState<Product[] | null>(null);

  useEffect(() => {
    api
      .get<{ items: Product[] }>(`/api/products?store_id=${storeId}`)
      .then((d) => setProducts(d.items ?? []))
      .catch(() => {});
  }, [storeId]);

  async function handleScan() {
    if (!scanValue.trim()) return;
    setError('');
    setLookupResults(null);
    try {
      const result = await lookupIdentifier(scanValue.trim());
      if (result.product) {
        setSelectedProductId(String(result.product.id));
        setScanValue('');
      } else if (result.ambiguous && result.products?.length) {
        setLookupResults(result.products);
      } else {
        setError('No product found for that identifier.');
      }
    } catch {
      setError('Lookup failed.');
    }
  }

  async function handleSubmit() {
    if (!selectedProductId) { setError('Select a product.'); return; }
    const delta = Number(quantityDelta);
    if (!delta || Number.isNaN(delta)) { setError('Enter a non-zero quantity delta.'); return; }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const body: Record<string, unknown> = {
        store_id: storeId,
        product_id: Number(selectedProductId),
        quantity_delta: delta,
      };
      if (note.trim()) body.note = note.trim();
      const occ = datetimeLocalToUtcIso(occurredAt);
      if (occ) body.occurred_at = occ;

      await api.post('/api/inventory/adjust', body);
      setSuccess(`Adjustment of ${delta > 0 ? '+' : ''}${delta} applied successfully.`);
      setSelectedProductId('');
      setQuantityDelta('');
      setOccurredAt('');
      setNote('');
      setScanValue('');
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Adjustment failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardTitle>Manual Adjustment</CardTitle>
      <CardDescription>
        Adjust inventory quantities directly. Use positive values to add and negative values to subtract.
      </CardDescription>

      {error && (
        <div className="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      {/* Scan / search */}
      <div className="flex gap-2 mt-4">
        <div className="flex-1">
          <Input
            label="Scan / Search Identifier"
            value={scanValue}
            onChange={(e) => setScanValue(e.target.value)}
            placeholder="Scan barcode or type identifier"
            onKeyDown={(e) => e.key === 'Enter' && handleScan()}
          />
        </div>
        <div className="flex items-end">
          <Button variant="secondary" onClick={handleScan}>
            Lookup
          </Button>
        </div>
      </div>

      {lookupResults && (
        <div className="mt-2 p-3 rounded-xl bg-amber-50 border border-amber-200">
          <p className="text-sm font-medium text-amber-800 mb-2">
            Ambiguous result - select a product:
          </p>
          <div className="flex flex-wrap gap-2">
            {lookupResults.map((p) => (
              <Button
                key={p.id}
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedProductId(String(p.id));
                  setLookupResults(null);
                  setScanValue('');
                }}
              >
                {p.sku} - {p.name}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <Select
          label="Product"
          value={selectedProductId}
          onChange={(e) => setSelectedProductId(e.target.value)}
          options={[
            { value: '', label: '-- Select Product --' },
            ...products.map((p) => ({
              value: String(p.id),
              label: `${p.sku} - ${p.name}`,
            })),
          ]}
        />
        <Input
          label="Quantity Delta"
          type="number"
          value={quantityDelta}
          onChange={(e) => setQuantityDelta(e.target.value)}
          placeholder="e.g. -5 or +10"
        />
        <Input
          label="Occurred At"
          type="datetime-local"
          value={occurredAt}
          onChange={(e) => setOccurredAt(e.target.value)}
        />
        <Input
          label="Note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Reason for adjustment"
        />
      </div>

      <div className="mt-4">
        <Button onClick={handleSubmit} disabled={busy}>
          Submit Adjustment
        </Button>
      </div>
    </Card>
  );
}

/* ================================================================== */
/*  PRODUCTS SECTION                                                   */
/* ================================================================== */

function ProductsSection({ storeId }: { storeId: number }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [summaries, setSummaries] = useState<Record<number, InventorySummary>>({});
  const [loading, setLoading] = useState(true);

  // Create form
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newIsActive, setNewIsActive] = useState(true);
  const [createError, setCreateError] = useState('');
  const [createBusy, setCreateBusy] = useState(false);

  // Edit dialog
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [editName, setEditName] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState('');

  // Delete dialog
  const [deleteProduct, setDeleteProduct] = useState<Product | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ items: Product[] }>(`/api/products?store_id=${storeId}`);
      const items = res.items ?? [];
      setProducts(items);

      // Load summaries for all products
      const now = new Date().toISOString();
      const summaryMap: Record<number, InventorySummary> = {};
      await Promise.allSettled(
        items.map(async (p) => {
          try {
            const s = await api.get<InventorySummary>(
              `/api/inventory/${p.id}/summary?store_id=${storeId}&as_of=${encodeURIComponent(now)}`,
            );
            summaryMap[p.id] = s;
          } catch {
            // skip
          }
        }),
      );
      setSummaries(summaryMap);
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  async function handleCreate() {
    if (!newSku.trim() || !newName.trim()) {
      setCreateError('SKU and Name are required.');
      return;
    }
    setCreateBusy(true);
    setCreateError('');
    try {
      const body: Record<string, unknown> = {
        sku: newSku.trim(),
        name: newName.trim(),
        is_active: newIsActive,
        store_id: storeId,
      };
      const priceDollars = parseFloat(newPrice);
      if (!Number.isNaN(priceDollars) && priceDollars >= 0) {
        body.price_cents = Math.round(priceDollars * 100);
      }
      await api.post<Product>('/api/products', body);
      setNewSku('');
      setNewName('');
      setNewPrice('');
      setNewIsActive(true);
      loadProducts();
    } catch (err: any) {
      setCreateError(err?.detail ?? err?.message ?? 'Failed to create product.');
    } finally {
      setCreateBusy(false);
    }
  }

  function openEdit(p: Product) {
    setEditProduct(p);
    setEditName(p.name);
    setEditPrice(p.price_cents != null ? (p.price_cents / 100).toFixed(2) : '');
    setEditIsActive(p.is_active);
    setEditError('');
  }

  async function handleEdit() {
    if (!editProduct) return;
    setEditBusy(true);
    setEditError('');
    try {
      const body: Record<string, unknown> = {
        name: editName.trim(),
        is_active: editIsActive,
      };
      const priceDollars = parseFloat(editPrice);
      if (!Number.isNaN(priceDollars) && priceDollars >= 0) {
        body.price_cents = Math.round(priceDollars * 100);
      }
      await api.put(`/api/products/${editProduct.id}`, body);
      setEditProduct(null);
      loadProducts();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Update failed.');
    } finally {
      setEditBusy(false);
    }
  }

  async function handleDelete() {
    if (!deleteProduct) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/api/products/${deleteProduct.id}`);
      setDeleteProduct(null);
      loadProducts();
    } catch {
      // silent
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Create Product */}
      <Card>
        <CardTitle>Create Product</CardTitle>
        <CardDescription>Add a new product to your store catalog.</CardDescription>

        {createError && (
          <div className="mt-3 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {createError}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          <Input
            label="SKU"
            value={newSku}
            onChange={(e) => setNewSku(e.target.value)}
            placeholder="e.g. PROD-001"
          />
          <Input
            label="Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Product name"
          />
          <Input
            label="Price ($)"
            type="number"
            min="0"
            step="0.01"
            value={newPrice}
            onChange={(e) => setNewPrice(e.target.value)}
            placeholder="0.00"
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-slate-700">Active</label>
            <label className="flex items-center gap-2 h-11 cursor-pointer">
              <input
                type="checkbox"
                checked={newIsActive}
                onChange={(e) => setNewIsActive(e.target.checked)}
                className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
              />
              <span className="text-sm text-slate-600">Product is active</span>
            </label>
          </div>
        </div>

        <div className="mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>
            Create Product
          </Button>
        </div>
      </Card>

      {/* Products Table */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>Products</CardTitle>
          <CardDescription>All products in this store with current inventory levels.</CardDescription>
        </div>

        {loading ? (
          <div className="p-5 text-sm text-muted">Loading products...</div>
        ) : products.length === 0 ? (
          <div className="p-5 text-sm text-muted">No products found.</div>
        ) : (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 px-5 font-medium">SKU</th>
                  <th className="py-2 px-3 font-medium">Name</th>
                  <th className="py-2 px-3 font-medium">Price</th>
                  <th className="py-2 px-3 font-medium">Status</th>
                  <th className="py-2 px-3 font-medium text-right">On Hand</th>
                  <th className="py-2 px-3 font-medium text-right">Avg Cost</th>
                  <th className="py-2 px-5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const summary = summaries[p.id];
                  return (
                    <tr key={p.id} className="border-b border-border/50 hover:bg-slate-50">
                      <td className="py-2.5 px-5 font-mono text-xs">{p.sku}</td>
                      <td className="py-2.5 px-3">{p.name}</td>
                      <td className="py-2.5 px-3">
                        {p.price_cents != null ? formatMoney(p.price_cents) : '-'}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={p.is_active ? 'success' : 'muted'}>
                          {p.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {summary ? summary.quantity_on_hand : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {summary?.weighted_average_cost_cents != null
                          ? formatMoney(summary.weighted_average_cost_cents)
                          : '-'}
                      </td>
                      <td className="py-2.5 px-5 text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEdit(p)}>
                            Edit
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteProduct(p)}>
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Edit Dialog */}
      <Dialog open={!!editProduct} onClose={() => setEditProduct(null)} title="Edit Product">
        {editError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {editError}
          </div>
        )}
        <div className="flex flex-col gap-4">
          <Input
            label="Name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
          <Input
            label="Price ($)"
            type="number"
            min="0"
            step="0.01"
            value={editPrice}
            onChange={(e) => setEditPrice(e.target.value)}
          />
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={editIsActive}
              onChange={(e) => setEditIsActive(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm text-slate-600">Active</span>
          </label>
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleEdit} disabled={editBusy}>
            Save
          </Button>
          <Button variant="secondary" onClick={() => setEditProduct(null)}>
            Cancel
          </Button>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteProduct} onClose={() => setDeleteProduct(null)} title="Delete Product">
        <p className="text-sm text-slate-600">
          Are you sure you want to delete{' '}
          <span className="font-semibold">{deleteProduct?.name}</span>? This action cannot be undone.
        </p>
        <div className="flex gap-2 mt-4">
          <Button variant="danger" onClick={handleDelete} disabled={deleteBusy}>
            Delete
          </Button>
          <Button variant="secondary" onClick={() => setDeleteProduct(null)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/* ================================================================== */
/*  LEDGER SECTION                                                     */
/* ================================================================== */

function LedgerSection({ storeId }: { storeId: number }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [asOf, setAsOf] = useState('');
  const [productLedger, setProductLedger] = useState<LedgerEntry[]>([]);
  const [masterLedger, setMasterLedger] = useState<LedgerEntry[]>([]);
  const [ledgerView, setLedgerView] = useState<'product' | 'master'>('master');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get<{ items: Product[] }>(`/api/products?store_id=${storeId}`)
      .then((d) => setProducts(d.items ?? []))
      .catch(() => {});
  }, [storeId]);

  async function loadProductLedger() {
    if (!selectedProductId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ store_id: String(storeId) });
      const occ = datetimeLocalToUtcIso(asOf);
      if (occ) params.set('as_of', occ);

      const res = await api.get<{ entries: LedgerEntry[] }>(
        `/api/inventory/${selectedProductId}/ledger?${params}`,
      );
      setProductLedger(res.entries ?? []);
    } catch {
      setProductLedger([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadMasterLedger() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ store_id: String(storeId) });
      const occ = datetimeLocalToUtcIso(asOf);
      if (occ) params.set('as_of', occ);

      const res = await api.get<{ entries: LedgerEntry[] }>(`/api/ledger?${params}`);
      setMasterLedger(res.entries ?? []);
    } catch {
      setMasterLedger([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (ledgerView === 'master') {
      loadMasterLedger();
    }
  }, [storeId, ledgerView]);

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`;

  function renderLedgerTable(entries: LedgerEntry[], showProduct: boolean) {
    if (loading) return <div className="p-5 text-sm text-muted">Loading...</div>;
    if (entries.length === 0) return <div className="p-5 text-sm text-muted">No entries found.</div>;

    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="py-2 px-5 font-medium">ID</th>
              {showProduct && <th className="py-2 px-3 font-medium">Product</th>}
              <th className="py-2 px-3 font-medium">Type</th>
              <th className="py-2 px-3 font-medium text-right">Qty Delta</th>
              <th className="py-2 px-3 font-medium text-right">Unit Cost</th>
              <th className="py-2 px-3 font-medium">Occurred At</th>
              <th className="py-2 px-5 font-medium">Note</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-border/50 hover:bg-slate-50">
                <td className="py-2 px-5 tabular-nums">{e.id}</td>
                {showProduct && (
                  <td className="py-2 px-3">
                    {e.product_id ? productName(e.product_id) : '-'}
                  </td>
                )}
                <td className="py-2 px-3">
                  <Badge variant={e.transaction_type === 'RECEIVE' ? 'success' : e.transaction_type === 'ADJUSTMENT' ? 'warning' : 'default'}>
                    {e.transaction_type}
                  </Badge>
                </td>
                <td className={`py-2 px-3 text-right tabular-nums font-medium ${e.quantity_delta > 0 ? 'text-emerald-600' : e.quantity_delta < 0 ? 'text-red-600' : ''}`}>
                  {e.quantity_delta > 0 ? '+' : ''}
                  {e.quantity_delta}
                </td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {formatMoney(e.unit_cost_cents)}
                </td>
                <td className="py-2 px-3 text-muted">{formatDateTime(e.occurred_at)}</td>
                <td className="py-2 px-5 text-muted">{e.note ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <Card>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex gap-2">
            <Button
              variant={ledgerView === 'master' ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setLedgerView('master')}
            >
              Master Ledger
            </Button>
            <Button
              variant={ledgerView === 'product' ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setLedgerView('product')}
            >
              Product Ledger
            </Button>
          </div>

          {ledgerView === 'product' && (
            <Select
              label="Product"
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              options={[
                { value: '', label: '-- Select Product --' },
                ...products.map((p) => ({
                  value: String(p.id),
                  label: `${p.sku} - ${p.name}`,
                })),
              ]}
            />
          )}

          <Input
            label="As Of"
            type="datetime-local"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
          />

          <Button
            variant="secondary"
            onClick={() => (ledgerView === 'product' ? loadProductLedger() : loadMasterLedger())}
          >
            Refresh
          </Button>
        </div>
      </Card>

      {/* Ledger Table */}
      <Card padding={false}>
        <div className="p-5 pb-0">
          <CardTitle>
            {ledgerView === 'master' ? 'Master Ledger' : 'Product Ledger'}
          </CardTitle>
          <CardDescription>
            {ledgerView === 'master'
              ? 'All inventory transactions across all products.'
              : 'Inventory transactions for the selected product.'}
          </CardDescription>
        </div>

        <div className="mt-4">
          {ledgerView === 'master'
            ? renderLedgerTable(masterLedger, true)
            : selectedProductId
              ? renderLedgerTable(productLedger, false)
              : <div className="p-5 text-sm text-muted">Select a product to view its ledger.</div>}
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== */
/*  LIFECYCLE SECTION                                                  */
/* ================================================================== */

function LifecycleSection({ storeId }: { storeId: number }) {
  const [documents, setDocuments] = useState<PendingDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ documents: PendingDocument[] }>(
        `/api/documents?store_id=${storeId}&status=APPROVED`,
      );
      setDocuments(res.documents ?? []);
    } catch {
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [storeId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  async function handlePost(docId: number) {
    setBusyId(docId);
    setError('');
    setSuccess('');
    try {
      await api.post(`/api/lifecycle/${docId}/post`);
      setSuccess(`Document #${docId} posted successfully.`);
      loadDocuments();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? `Failed to post document #${docId}.`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card padding={false}>
      <div className="p-5 pb-0">
        <CardTitle>Pending Transactions</CardTitle>
        <CardDescription>
          Approved documents awaiting posting. Post them to finalize inventory changes.
        </CardDescription>
      </div>

      {error && (
        <div className="mx-5 mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mx-5 mt-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      )}

      <div className="mt-4">
        {loading ? (
          <div className="p-5 text-sm text-muted">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="p-5 text-sm text-muted">No approved documents pending posting.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 px-5 font-medium">ID</th>
                  <th className="py-2 px-3 font-medium">Type</th>
                  <th className="py-2 px-3 font-medium">Document #</th>
                  <th className="py-2 px-3 font-medium">Status</th>
                  <th className="py-2 px-5 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b border-border/50 hover:bg-slate-50">
                    <td className="py-2.5 px-5 tabular-nums">{doc.id}</td>
                    <td className="py-2.5 px-3">
                      <Badge>{doc.document_type}</Badge>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs">{doc.document_number}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant="warning">{doc.status}</Badge>
                    </td>
                    <td className="py-2.5 px-5 text-right">
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={busyId === doc.id}
                        onClick={() => handlePost(doc.id)}
                      >
                        {busyId === doc.id ? 'Posting...' : 'Post'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="p-5 pt-3">
        <Button variant="secondary" size="sm" onClick={loadDocuments}>
          Refresh
        </Button>
      </div>
    </Card>
  );
}
