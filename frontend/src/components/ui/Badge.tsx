import type { ReactNode } from 'react';

type Variant = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'muted';

const variantClasses: Record<Variant, string> = {
  default: 'bg-slate-100 text-slate-700',
  primary: 'bg-primary-light text-primary',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  danger: 'bg-red-50 text-red-700',
  muted: 'bg-slate-50 text-muted',
};

interface BadgeProps {
  variant?: Variant;
  children: ReactNode;
  className?: string;
}

export function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
}
