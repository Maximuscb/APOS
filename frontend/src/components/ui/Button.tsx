import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'warning';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover shadow-sm active:shadow-inner',
  secondary: 'bg-white text-slate-700 border border-border hover:bg-slate-50 shadow-sm active:shadow-inner',
  danger: 'bg-danger text-white hover:bg-danger-hover shadow-sm active:shadow-inner',
  ghost: 'text-slate-600 hover:bg-slate-100 active:bg-slate-200',
  warning: 'bg-warning text-white hover:bg-amber-600 shadow-sm active:shadow-inner',
};

const sizeClasses: Record<Size, string> = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-11 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
};

export function Button({ variant = 'primary', size = 'md', className = '', children, ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-medium
        transition-all duration-150 ease-out
        active:translate-y-0.5 active:scale-[0.98]
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary
        disabled:opacity-50 disabled:pointer-events-none cursor-pointer
        ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
