import { NavLink } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

interface NavItem {
  path: string;
  label: string;
  minRole?: 'manager' | 'admin';
  permissions?: string[];
}

const navItems: NavItem[] = [
  { path: '/operations/overview', label: 'Overview' },
  { path: '/operations/products', label: 'Products', permissions: ['VIEW_INVENTORY', 'MANAGE_PRODUCTS'] },
  { path: '/operations/registers', label: 'Registers', permissions: ['MANAGE_REGISTER', 'CREATE_REGISTER'] },
  { path: '/operations/devices', label: 'Devices', permissions: ['MANAGE_REGISTER'] },
  { path: '/operations/payments', label: 'Payments', permissions: ['REFUND_PAYMENT', 'VIEW_SALES_REPORTS'] },
  { path: '/operations/workflows', label: 'Workflows', permissions: ['PROCESS_RETURN', 'CREATE_TRANSFERS', 'CREATE_COUNTS'] },
  { path: '/operations/documents', label: 'Documents', permissions: ['VIEW_DOCUMENTS'] },
  { path: '/operations/analytics', label: 'Analytics', permissions: ['VIEW_ANALYTICS'] },
  { path: '/operations/imports', label: 'Imports', permissions: ['CREATE_IMPORTS'] },
  { path: '/operations/timekeeping', label: 'Timekeeping', permissions: ['VIEW_TIMEKEEPING', 'MANAGE_TIMEKEEPING'] },
  { path: '/operations/audits', label: 'Audits', permissions: ['VIEW_AUDIT_LOG'] },
  { path: '/operations/users', label: 'Users', minRole: 'manager' },
  { path: '/operations/overrides', label: 'Overrides', permissions: ['MANAGE_PERMISSIONS'] },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { hasRole, hasPermission } = useAuth();

  return (
    <nav className="flex flex-col gap-1 p-3">
      {navItems.map((item) => {
        if (item.minRole && !hasRole(item.minRole)) return null;
        if (item.permissions && !item.permissions.some((p) => hasPermission(p))) return null;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 h-10 rounded-xl text-sm font-medium transition-colors
              ${isActive ? 'bg-primary-light text-primary' : 'text-slate-600 hover:bg-slate-100'}`
            }
          >
            {item.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
