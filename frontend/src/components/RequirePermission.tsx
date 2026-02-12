import type { ReactNode } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Card, CardTitle, CardDescription } from '@/components/ui/Card';

interface RequirePermissionProps {
  children: ReactNode;
  /** User needs at least ONE of these permissions to access */
  anyOf: string[];
}

export function RequirePermission({ children, anyOf }: RequirePermissionProps) {
  const { hasPermission } = useAuth();

  if (anyOf.some((p) => hasPermission(p))) return <>{children}</>;

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      <Card>
        <CardTitle>Access Denied</CardTitle>
        <CardDescription>
          You do not have the required permissions to access this page.
        </CardDescription>
      </Card>
    </div>
  );
}
