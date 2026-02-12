import { useStore } from '@/context/StoreContext';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Input';
import type { ReportFiltersState } from './types';

interface ReportFiltersProps {
  filters: ReportFiltersState;
  onChange: (filters: ReportFiltersState) => void;
  onRun: () => void;
  loading?: boolean;
}

function todayStr() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString().slice(0, 16);
}

function datePreset(days: number): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - days);
  start.setHours(0, 0, 0, 0);
  return {
    start: start.toISOString().slice(0, 16),
    end: end.toISOString().slice(0, 16),
  };
}

function startOfWeek(): string {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d.toISOString().slice(0, 16);
}

function startOfMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d.toISOString().slice(0, 16);
}

export function ReportFilters({ filters, onChange, onRun, loading }: ReportFiltersProps) {
  const { stores } = useStore();

  const set = (partial: Partial<ReportFiltersState>) => onChange({ ...filters, ...partial });
  const now = new Date().toISOString().slice(0, 16);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-4 items-end">
        <Select
          label="Store"
          value={filters.storeId}
          onChange={(e) => set({ storeId: e.target.value })}
          options={stores.map((s) => ({ value: String(s.id), label: s.name }))}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700 mt-6">
          <input
            type="checkbox"
            checked={filters.includeChildren}
            onChange={(e) => set({ includeChildren: e.target.checked })}
            className="rounded border-slate-300"
          />
          Include child stores
        </label>
        <Input
          label="From"
          type="datetime-local"
          value={filters.startDate}
          onChange={(e) => set({ startDate: e.target.value })}
        />
        <Input
          label="To"
          type="datetime-local"
          value={filters.endDate}
          onChange={(e) => set({ endDate: e.target.value })}
        />
        <Button variant="primary" onClick={onRun} disabled={loading}>
          {loading ? 'Loading...' : 'Run Report'}
        </Button>
      </div>
      <div className="flex gap-2">
        <button
          className="text-xs px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          onClick={() => set({ startDate: todayStr(), endDate: now })}
        >
          Today
        </button>
        <button
          className="text-xs px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          onClick={() => set({ startDate: startOfWeek(), endDate: now })}
        >
          This Week
        </button>
        <button
          className="text-xs px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          onClick={() => set({ startDate: startOfMonth(), endDate: now })}
        >
          This Month
        </button>
        <button
          className="text-xs px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          onClick={() => {
            const p = datePreset(30);
            set({ startDate: p.start, endDate: p.end });
          }}
        >
          Last 30 Days
        </button>
        <button
          className="text-xs px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          onClick={() => {
            const p = datePreset(90);
            set({ startDate: p.start, endDate: p.end });
          }}
        >
          Last 90 Days
        </button>
      </div>
    </div>
  );
}
