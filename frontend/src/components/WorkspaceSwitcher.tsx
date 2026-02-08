import { useLocation, useNavigate } from 'react-router-dom';

const workspaces = [
  { path: '/register', label: 'Register' },
  { path: '/inventory', label: 'Inventory' },
  { path: '/operations', label: 'Operations' },
];

export function WorkspaceSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();

  const current = workspaces.find((w) => location.pathname.startsWith(w.path))?.path ?? '/register';

  return (
    <div className="flex bg-slate-100 rounded-xl p-1 gap-1">
      {workspaces.map((w) => (
        <button
          key={w.path}
          onClick={() => navigate(w.path)}
          className={`px-4 h-9 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap
            ${current === w.path
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-muted hover:text-slate-700'
            }`}
        >
          {w.label}
        </button>
      ))}
    </div>
  );
}
