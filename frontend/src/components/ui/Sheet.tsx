import { type ReactNode, useEffect } from 'react';

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: 'right' | 'bottom';
}

export function Sheet({ open, onClose, title, children, side = 'right' }: SheetProps) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  const positionClass = side === 'bottom'
    ? 'inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl'
    : 'inset-y-0 right-0 w-full max-w-md';

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />
      <div className={`fixed ${positionClass} bg-white shadow-xl overflow-y-auto`}>
        <div className="flex items-center justify-between p-5 border-b border-border sticky top-0 bg-white z-10">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="h-9 w-9 flex items-center justify-center rounded-xl hover:bg-slate-100 text-slate-400 cursor-pointer">
            ✕
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
