import { useLocation, useNavigate } from 'react-router-dom';

const workspaces = [
  { matchPrefixes: ['/sales', '/register'], targetPath: '/sales', label: 'Sales' },
  { matchPrefixes: ['/inventory'], targetPath: '/inventory', label: 'Inventory' },
  { matchPrefixes: ['/operations'], targetPath: '/operations/analytics', label: 'Operations' },
];

export function WorkspaceSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();

  const current = workspaces.find((w) => w.matchPrefixes.some((prefix) => location.pathname.startsWith(prefix)))?.targetPath ?? '/sales';

  return (
    <div className="flex bg-slate-100 rounded-xl p-1 gap-1">
      {workspaces.map((w) => (
        <button
          key={w.targetPath}
          onClick={() => navigate(w.targetPath)}
          className={`px-4 h-9 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap
            ${current === w.targetPath
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
