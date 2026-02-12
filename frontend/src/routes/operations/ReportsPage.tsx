import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useStore } from '@/context/StoreContext';
import { Tabs } from '@/components/ui/Tabs';
import { SalesReports } from './reports/SalesReports';
import { ProfitabilityReports } from './reports/ProfitabilityReports';
import { InventoryReports } from './reports/InventoryReports';
import { VendorReports } from './reports/VendorReports';
import { CashRegisterReports } from './reports/CashRegisterReports';
import { WorkforceReports } from './reports/WorkforceReports';
import { CustomerReports } from './reports/CustomerReports';
import { RiskReports } from './reports/RiskReports';
import { ManualReports } from './reports/ManualReports';
import type { ReportFiltersState } from './reports/types';

const TABS = [
  { value: 'sales', label: 'Sales & Revenue' },
  { value: 'profitability', label: 'Profitability' },
  { value: 'inventory', label: 'Inventory' },
  { value: 'vendor', label: 'Vendor' },
  { value: 'cash', label: 'Cash & Register' },
  { value: 'workforce', label: 'Workforce' },
  { value: 'customer', label: 'Customer & Rewards' },
  { value: 'risk', label: 'Risk & Compliance' },
  { value: 'manual', label: 'Manual Reports' },
];

function defaultFilters(defaultStoreId: string): ReportFiltersState {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  start.setHours(0, 0, 0, 0);
  return {
    storeId: defaultStoreId,
    includeChildren: false,
    startDate: start.toISOString().slice(0, 16),
    endDate: end.toISOString().slice(0, 16),
  };
}

export function ReportsPage() {
  const { hasPermission, isDeveloper } = useAuth();
  const { currentStoreId, stores } = useStore();
  const [activeTab, setActiveTab] = useState('sales');
  const [filters, setFilters] = useState<ReportFiltersState>(() =>
    defaultFilters(currentStoreId ? String(currentStoreId) : ''),
  );

  useEffect(() => {
    if (filters.storeId) return;
    const fallbackStoreId = currentStoreId
      ? String(currentStoreId)
      : stores.length > 0
        ? String(stores[0].id)
        : '';
    if (!fallbackStoreId) return;
    setFilters((prev) => ({ ...prev, storeId: fallbackStoreId }));
  }, [filters.storeId, currentStoreId, stores]);

  // Filter tabs by permissions
  const visibleTabs = TABS.filter((tab) => {
    if (isDeveloper) return true;
    switch (tab.value) {
      case 'sales': return hasPermission('VIEW_SALES_REPORTS');
      case 'profitability': return hasPermission('VIEW_COGS');
      case 'inventory': return hasPermission('VIEW_INVENTORY');
      case 'vendor': return hasPermission('VIEW_VENDORS');
      case 'cash': return hasPermission('MANAGE_REGISTER');
      case 'workforce': return hasPermission('VIEW_TIMEKEEPING');
      case 'customer': return hasPermission('VIEW_SALES_REPORTS');
      case 'risk': return hasPermission('VIEW_AUDIT_LOG');
      case 'manual': return hasPermission('VIEW_DOCUMENTS');
      default: return true;
    }
  });

  // If active tab is not visible, switch to first visible
  useEffect(() => {
    if (visibleTabs.length > 0 && !visibleTabs.find((t) => t.value === activeTab)) {
      setActiveTab(visibleTabs[0].value);
    }
  }, [visibleTabs, activeTab]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Reports Dashboard</h1>
        <p className="text-sm text-muted mt-1">
          Analyze your business data across all managed stores.
        </p>
      </div>

      <Tabs tabs={visibleTabs} value={activeTab} onValueChange={setActiveTab} />

      <div>
        {activeTab === 'sales' && <SalesReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'profitability' && <ProfitabilityReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'inventory' && <InventoryReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'vendor' && <VendorReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'cash' && <CashRegisterReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'workforce' && <WorkforceReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'customer' && <CustomerReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'risk' && <RiskReports filters={filters} onFiltersChange={setFilters} />}
        {activeTab === 'manual' && <ManualReports />}
      </div>
    </div>
  );
}
