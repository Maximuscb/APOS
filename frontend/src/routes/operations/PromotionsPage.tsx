import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { useStore } from '@/context/StoreContext';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';

interface Promotion {
  id: number;
  name: string;
  description: string | null;
  promo_type: string;
  discount_value: number;
  applies_to: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  created_at: string;
}

const promoTypeLabels: Record<string, string> = {
  PERCENTAGE: '% Off',
  FIXED_AMOUNT: '$ Off',
  BOGO: 'BOGO',
  BUNDLE: 'Bundle',
};

function formatDiscount(type: string, value: number): string {
  if (type === 'PERCENTAGE') return `${(value / 100).toFixed(1)}%`;
  if (type === 'FIXED_AMOUNT') return `$${(value / 100).toFixed(2)}`;
  return String(value);
}

export function PromotionsPage() {
  const { currentStoreId } = useStore();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('MANAGE_PROMOTIONS');

  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [promoType, setPromoType] = useState('PERCENTAGE');
  const [discountValue, setDiscountValue] = useState('');

  const fetchPromotions = useCallback(() => {
    if (!currentStoreId) return;
    setLoading(true);
    api.get<Promotion[]>(`/api/promotions?store_id=${currentStoreId}`)
      .then(setPromotions)
      .catch(() => setPromotions([]))
      .finally(() => setLoading(false));
  }, [currentStoreId]);

  useEffect(() => { fetchPromotions(); }, [fetchPromotions]);

  const handleCreate = async () => {
    if (!name.trim() || !discountValue) return;
    await api.post('/api/promotions', {
      name,
      description: description || undefined,
      promo_type: promoType,
      discount_value: Number(discountValue),
      store_id: currentStoreId,
    });
    setShowCreate(false);
    setName('');
    setDescription('');
    setPromoType('PERCENTAGE');
    setDiscountValue('');
    fetchPromotions();
  };

  const toggleActive = async (id: number, isActive: boolean) => {
    await api.patch(`/api/promotions/${id}`, { is_active: !isActive });
    fetchPromotions();
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Promotions</h1>
        {canManage && (
          <Button onClick={() => setShowCreate(true)}>+ New Promotion</Button>
        )}
      </div>

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : promotions.length === 0 ? (
        <Card className="p-8 text-center text-muted">No promotions configured.</Card>
      ) : (
        <div className="space-y-3">
          {promotions.map((p) => (
            <Card key={p.id} className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={p.is_active ? 'primary' : 'default'}>
                    {p.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  <Badge variant="default">{promoTypeLabels[p.promo_type] ?? p.promo_type}</Badge>
                  <span className="text-sm font-bold text-emerald-700">
                    {formatDiscount(p.promo_type, p.discount_value)}
                  </span>
                </div>
                <h3 className="font-semibold text-slate-900">{p.name}</h3>
                {p.description && <p className="text-sm text-muted mt-1">{p.description}</p>}
                <div className="flex gap-4 mt-1 text-xs text-muted">
                  <span>Applies to: {p.applies_to.replace(/_/g, ' ')}</span>
                  {p.start_date && <span>From: {formatDate(p.start_date)}</span>}
                  {p.end_date && <span>To: {formatDate(p.end_date)}</span>}
                </div>
              </div>
              {canManage && (
                <Button size="sm" variant="secondary" onClick={() => toggleActive(p.id, p.is_active)}>
                  {p.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              )}
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showCreate} onClose={() => setShowCreate(false)} title="New Promotion">
        <div className="space-y-4 p-1">
          <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea
              className="w-full rounded-xl border border-border px-3 py-2 text-sm min-h-[60px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
            <select
              className="w-full rounded-xl border border-border px-3 py-2 text-sm"
              value={promoType}
              onChange={(e) => setPromoType(e.target.value)}
            >
              <option value="PERCENTAGE">Percentage Off</option>
              <option value="FIXED_AMOUNT">Fixed Amount Off</option>
              <option value="BOGO">Buy One Get One</option>
              <option value="BUNDLE">Bundle</option>
            </select>
          </div>
          <Input
            label={promoType === 'PERCENTAGE' ? 'Discount (basis points, e.g. 1000 = 10%)' : 'Discount (cents)'}
            type="number"
            value={discountValue}
            onChange={(e) => setDiscountValue(e.target.value)}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
