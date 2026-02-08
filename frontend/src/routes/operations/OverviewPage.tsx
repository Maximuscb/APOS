import { useStore } from "@/context/StoreContext";
import { useAuth } from "@/context/AuthContext";
import { Card, CardTitle } from "@/components/ui/Card";

export default function OverviewPage() {
  const { currentStoreName, currentStoreId } = useStore();
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Operations</h1>
        <p className="text-sm text-muted mt-1">
          Welcome back, {user?.name ?? user?.username}. Managing {currentStoreName ?? `Store #${currentStoreId}`}.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card>
          <CardTitle>Products</CardTitle>
          <p className="text-sm text-muted">Manage your product catalog and inventory</p>
        </Card>
        <Card>
          <CardTitle>Registers</CardTitle>
          <p className="text-sm text-muted">View register status and session history</p>
        </Card>
        <Card>
          <CardTitle>Analytics</CardTitle>
          <p className="text-sm text-muted">Sales trends and performance reports</p>
        </Card>
      </div>
    </div>
  );
}
