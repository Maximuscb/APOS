interface TabsProps {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}

export function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <div className="flex gap-1 bg-slate-100 rounded-xl p-1 overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`px-4 h-9 rounded-lg text-sm font-medium whitespace-nowrap transition-colors cursor-pointer
            ${active === tab
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-muted hover:text-slate-700'
            }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
