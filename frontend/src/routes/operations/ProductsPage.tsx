import { useCallback, useEffect, useState } from 'react';
import { useStore } from '@/context/StoreContext';
import { api } from '@/lib/api';
import { formatMoney } from '@/lib/format';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';

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

type InventorySummary = {
  store_id: number;
  product_id: number;
  quantity_on_hand: number;
  weighted_average_cost_cents: number | null;
  recent_unit_cost_cents: number | null;
};

type ProductRow = Product & {
  quantity_on_hand: number | null;
  weighted_average_cost_cents: number | null;
  recent_unit_cost_cents: number | null;
};

/* ------------------------------------------------------------------ */
/*  Price validation                                                   */
/* ------------------------------------------------------------------ */

const MAX_PRICE_CENTS = 999999999; // $9,999,999.99

function parsePriceDollars(raw: string): { valid: boolean; cents: number } {
  const trimmed = raw.trim();
  if (trimmed === '') return { valid: true, cents: 0 };
  // reject scientific notation and negatives
  if (/[eE]/.test(trimmed) || trimmed.startsWith('-')) return { valid: false, cents: 0 };
  const value = parseFloat(trimmed);
  if (Number.isNaN(value) || value < 0) return { valid: false, cents: 0 };
  const cents = Math.round(value * 100);
  if (cents > MAX_PRICE_CENTS) return { valid: false, cents: 0 };
  return { valid: true, cents };
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function ProductsPage() {
  const { currentStoreId: storeId } = useStore();

  const [products, setProducts] = useState<ProductRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // As-of date filter
  const [asOfDate, setAsOfDate] = useState('');

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [newIsActive, setNewIsActive] = useState(true);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState('');

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

  /* ---- Load products + inventory summaries ---- */

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ store_id: String(storeId) });
      if (asOfDate) {
        const d = new Date(asOfDate);
        if (!Number.isNaN(d.getTime())) params.set('as_of', d.toISOString());
      }

      const res = await api.get<{ items: Product[] }>(`/api/products?${params}`);
      const items = res.items ?? [];

      // Fetch inventory summaries in parallel
      const asOfParam = asOfDate
        ? new Date(asOfDate).toISOString()
        : new Date().toISOString();

      const summaryMap: Record<number, InventorySummary> = {};
      await Promise.allSettled(
        items.map(async (p) => {
          try {
            const s = await api.get<InventorySummary>(
              `/api/inventory/${p.id}/summary?store_id=${storeId}&as_of=${encodeURIComponent(asOfParam)}`,
            );
            summaryMap[p.id] = s;
          } catch {
            // skip
          }
        }),
      );

      const rows: ProductRow[] = items.map((p) => ({
        ...p,
        quantity_on_hand: summaryMap[p.id]?.quantity_on_hand ?? null,
        weighted_average_cost_cents: summaryMap[p.id]?.weighted_average_cost_cents ?? null,
        recent_unit_cost_cents: summaryMap[p.id]?.recent_unit_cost_cents ?? null,
      }));

      setProducts(rows);
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Failed to load products.');
    } finally {
      setLoading(false);
    }
  }, [storeId, asOfDate]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  /* ---- Create product ---- */

  async function handleCreate() {
    if (!newSku.trim() || !newName.trim()) {
      setCreateError('SKU and Name are required.');
      return;
    }
    const priceResult = parsePriceDollars(newPrice);
    if (!priceResult.valid) {
      setCreateError('Invalid price. Max $9,999,999.99. No negatives or scientific notation.');
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
      if (newPrice.trim() !== '') {
        body.price_cents = priceResult.cents;
      }
      await api.post<Product>('/api/products', body);
      setNewSku('');
      setNewName('');
      setNewPrice('');
      setNewIsActive(true);
      setShowCreate(false);
      loadProducts();
    } catch (err: any) {
      setCreateError(err?.detail ?? err?.message ?? 'Failed to create product.');
    } finally {
      setCreateBusy(false);
    }
  }

  /* ---- Edit product ---- */

  function openEdit(p: Product) {
    setEditProduct(p);
    setEditName(p.name);
    setEditPrice(p.price_cents != null ? (p.price_cents / 100).toFixed(2) : '');
    setEditIsActive(p.is_active);
    setEditError('');
  }

  async function handleEdit() {
    if (!editProduct) return;
    const priceResult = parsePriceDollars(editPrice);
    if (!priceResult.valid) {
      setEditError('Invalid price. Max $9,999,999.99. No negatives or scientific notation.');
      return;
    }

    setEditBusy(true);
    setEditError('');
    try {
      const body: Record<string, unknown> = {
        name: editName.trim(),
        is_active: editIsActive,
      };
      if (editPrice.trim() !== '') {
        body.price_cents = priceResult.cents;
      }
      await api.patch(`/api/products/${editProduct.id}`, body);
      setEditProduct(null);
      loadProducts();
    } catch (err: any) {
      setEditError(err?.detail ?? err?.message ?? 'Update failed.');
    } finally {
      setEditBusy(false);
    }
  }

  /* ---- Delete product ---- */

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

  /* ---- Table columns ---- */

  const columns = [
    {
      key: 'sku',
      header: 'SKU',
      render: (row: ProductRow) => (
        <span className="font-mono text-xs">{row.sku}</span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      render: (row: ProductRow) => <span>{row.name}</span>,
    },
    {
      key: 'price',
      header: 'Price',
      render: (row: ProductRow) => (
        <span>{row.price_cents != null ? formatMoney(row.price_cents) : '-'}</span>
      ),
    },
    {
      key: 'on_hand',
      header: 'On Hand',
      className: 'text-right',
      render: (row: ProductRow) => (
        <span className="tabular-nums">{row.quantity_on_hand ?? '-'}</span>
      ),
    },
    {
      key: 'wac',
      header: 'WAC',
      className: 'text-right',
      render: (row: ProductRow) => (
        <span className="tabular-nums">
          {row.weighted_average_cost_cents != null
            ? formatMoney(row.weighted_average_cost_cents)
            : '-'}
        </span>
      ),
    },
    {
      key: 'recent_cost',
      header: 'Recent Cost',
      className: 'text-right',
      render: (row: ProductRow) => (
        <span className="tabular-nums">
          {row.recent_unit_cost_cents != null
            ? formatMoney(row.recent_unit_cost_cents)
            : '-'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: ProductRow) => (
        <Badge variant={row.is_active ? 'success' : 'muted'}>
          {row.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (row: ProductRow) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDeleteProduct(row)}>
            Delete
          </Button>
        </div>
      ),
    },
  ];

  /* ---- Render ---- */

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Products</h1>
          <p className="text-sm text-muted mt-1">
            Manage your product catalog and inventory levels.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create Product</Button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* As-of filter */}
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Input
            label="As-of Date"
            type="datetime-local"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
          />
          <Button variant="secondary" size="sm" onClick={loadProducts}>
            Refresh
          </Button>
          {asOfDate && (
            <Button variant="ghost" size="sm" onClick={() => setAsOfDate('')}>
              Clear
            </Button>
          )}
        </div>
      </Card>

      {/* Products table */}
      {loading ? (
        <p className="text-sm text-muted">Loading products...</p>
      ) : (
        <DataTable
          columns={columns}
          data={products}
          emptyMessage="No products found."
        />
      )}

      {/* Create Product Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="Create Product">
        {createError && (
          <div className="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {createError}
          </div>
        )}
        <div className="flex flex-col gap-4">
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
            label="Price (USD)"
            type="number"
            min="0"
            step="0.01"
            value={newPrice}
            onChange={(e) => setNewPrice(e.target.value)}
            placeholder="0.00"
          />
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={newIsActive}
              onChange={(e) => setNewIsActive(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm text-slate-600">Product is active</span>
          </label>
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={handleCreate} disabled={createBusy}>
            {createBusy ? 'Creating...' : 'Create'}
          </Button>
          <Button variant="secondary" onClick={() => setShowCreate(false)}>
            Cancel
          </Button>
        </div>
      </Dialog>

      {/* Edit Product Dialog */}
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
            label="Price (USD)"
            type="number"
            min="0"
            step="0.01"
            value={editPrice}
            onChange={(e) => setEditPrice(e.target.value)}
            placeholder="0.00"
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
            {editBusy ? 'Saving...' : 'Save'}
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
            {deleteBusy ? 'Deleting...' : 'Delete'}
          </Button>
          <Button variant="secondary" onClick={() => setDeleteProduct(null)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
