import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { SidebarNav } from '@/components/SidebarNav';
import { Sheet } from '@/components/ui/Sheet';

export function OperationsLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 shrink-0 border-r border-border bg-white overflow-y-auto">
        <div className="w-full">
          <div className="px-4 pt-4 pb-2">
            <h2 className="text-sm font-semibold text-muted uppercase tracking-wider">Operations</h2>
          </div>
          <SidebarNav />
        </div>
      </aside>

      {/* Mobile sidebar toggle */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="md:hidden fixed bottom-6 left-6 h-12 w-12 bg-primary text-white rounded-2xl shadow-lg flex items-center justify-center z-30 cursor-pointer text-lg"
      >
        ☰
      </button>

      <Sheet open={sidebarOpen} onClose={() => setSidebarOpen(false)} title="Navigation" side="bottom">
        <SidebarNav onNavigate={() => setSidebarOpen(false)} />
      </Sheet>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
