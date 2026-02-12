import { NavLink } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

interface NavItem {
  path: string;
  label: string;
  permissions?: string[];
}

const navItems: NavItem[] = [
  { path: '/operations/dashboard', label: 'Dashboard' },
  { path: '/operations/analytics', label: 'Analytics', permissions: ['VIEW_ANALYTICS'] },
  { path: '/operations/devices', label: 'Devices', permissions: ['CREATE_SALE', 'MANAGE_REGISTER'] },
  { path: '/operations/reports', label: 'Reports', permissions: ['VIEW_DOCUMENTS'] },
  { path: '/operations/communications', label: 'Communications', permissions: ['VIEW_COMMUNICATIONS', 'MANAGE_COMMUNICATIONS'] },
  { path: '/operations/promotions', label: 'Promotions', permissions: ['VIEW_PROMOTIONS', 'MANAGE_PROMOTIONS'] },
  { path: '/operations/services', label: 'Services', permissions: ['CREATE_IMPORTS'] },
  { path: '/operations/timekeeping', label: 'Timekeeping', permissions: ['VIEW_TIMEKEEPING', 'MANAGE_TIMEKEEPING'] },
  { path: '/operations/vendors', label: 'Vendors', permissions: ['VIEW_VENDORS', 'MANAGE_VENDORS'] },
  { path: '/operations/users', label: 'Users', permissions: ['VIEW_USERS', 'CREATE_USER', 'EDIT_USER', 'ASSIGN_ROLES', 'DEACTIVATE_USER'] },

  { path: '/operations/settings', label: 'Settings', permissions: ['VIEW_STORES', 'MANAGE_STORES'] },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { hasPermission, isDeveloper } = useAuth();

  return (
    <nav className="flex flex-col gap-1 p-3">
      {navItems.map((item) => {
        if (item.path === '/operations/developer' && !isDeveloper) return null;
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
      {isDeveloper && (
        <NavLink
          to="/operations/developer"
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-2 px-3 h-10 rounded-xl text-sm font-medium transition-colors
              ${isActive ? 'bg-primary-light text-primary' : 'text-slate-600 hover:bg-slate-100'}`
          }
        >
          Developer
        </NavLink>
      )}
    </nav>
  );
}
