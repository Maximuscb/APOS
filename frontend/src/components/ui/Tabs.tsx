type TabItem = { value: string; label: string };

interface TabsProps {
  tabs: (string | TabItem)[];
  active?: string;
  value?: string;
  onChange?: (tab: string) => void;
  onValueChange?: (value: string) => void;
}

export function Tabs({ tabs, active, value, onChange, onValueChange }: TabsProps) {
  const currentValue = active ?? value ?? '';
  const handleChange = onChange ?? onValueChange ?? (() => {});

  return (
    <div className="flex gap-1 bg-slate-100 rounded-xl p-1 overflow-x-auto">
      {tabs.map((tab) => {
        const tabValue = typeof tab === 'string' ? tab : tab.value;
        const tabLabel = typeof tab === 'string' ? tab : tab.label;
        return (
          <button
            key={tabValue}
            onClick={() => handleChange(tabValue)}
            className={`px-4 h-9 rounded-lg text-sm font-medium whitespace-nowrap transition-colors cursor-pointer
              ${currentValue === tabValue
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-muted hover:text-slate-700'
              }`}
          >
            {tabLabel}
          </button>
        );
      })}
    </div>
  );
}
