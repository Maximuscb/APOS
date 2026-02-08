import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { StoreProvider } from '@/context/StoreContext';
import { AppShell } from '@/components/AppShell';
import { LoginPage } from '@/routes/auth/LoginPage';
import { RegisterPage } from '@/routes/register/RegisterPage';
import { InventoryPage } from '@/routes/inventory/InventoryPage';
import { OperationsLayout } from '@/routes/operations/OperationsLayout';
import { lazy, Suspense, type ReactNode } from 'react';

// Lazy-load operations sub-pages
const OverviewPage = lazy(() => import('@/routes/operations/OverviewPage'));
const ProductsPage = lazy(() => import('@/routes/operations/ProductsPage'));
const RegistersPage = lazy(() => import('@/routes/operations/RegistersPage'));
const DevicesPage = lazy(() => import('@/routes/operations/DevicesPage'));
const PaymentsPage = lazy(() => import('@/routes/operations/PaymentsPage'));
const WorkflowsPage = lazy(() => import('@/routes/operations/WorkflowsPage'));
const DocumentsPage = lazy(() => import('@/routes/operations/DocumentsPage'));
const AnalyticsPage = lazy(() => import('@/routes/operations/AnalyticsPage'));
const ImportsPage = lazy(() => import('@/routes/operations/ImportsPage'));
const TimekeepingPage = lazy(() => import('@/routes/operations/TimekeepingPage'));
const AuditsPage = lazy(() => import('@/routes/operations/AuditsPage'));
const UsersPage = lazy(() => import('@/routes/operations/UsersPage'));
const OverridesPage = lazy(() => import('@/routes/operations/OverridesPage'));

function AuthGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Loading() {
  return (
    <div className="flex items-center justify-center py-20">
      <p className="text-muted">Loading...</p>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <StoreProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route
              element={
                <AuthGuard>
                  <AppShell />
                </AuthGuard>
              }
            >
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/inventory" element={<InventoryPage />} />

              <Route path="/operations" element={<OperationsLayout />}>
                <Route index element={<Suspense fallback={<Loading />}><OverviewPage /></Suspense>} />
                <Route path="products" element={<Suspense fallback={<Loading />}><ProductsPage /></Suspense>} />
                <Route path="registers" element={<Suspense fallback={<Loading />}><RegistersPage /></Suspense>} />
                <Route path="devices" element={<Suspense fallback={<Loading />}><DevicesPage /></Suspense>} />
                <Route path="payments" element={<Suspense fallback={<Loading />}><PaymentsPage /></Suspense>} />
                <Route path="workflows" element={<Suspense fallback={<Loading />}><WorkflowsPage /></Suspense>} />
                <Route path="documents" element={<Suspense fallback={<Loading />}><DocumentsPage /></Suspense>} />
                <Route path="analytics" element={<Suspense fallback={<Loading />}><AnalyticsPage /></Suspense>} />
                <Route path="imports" element={<Suspense fallback={<Loading />}><ImportsPage /></Suspense>} />
                <Route path="timekeeping" element={<Suspense fallback={<Loading />}><TimekeepingPage /></Suspense>} />
                <Route path="audits" element={<Suspense fallback={<Loading />}><AuditsPage /></Suspense>} />
                <Route path="users" element={<Suspense fallback={<Loading />}><UsersPage /></Suspense>} />
                <Route path="overrides" element={<Suspense fallback={<Loading />}><OverridesPage /></Suspense>} />
              </Route>

              <Route path="*" element={<Navigate to="/operations" replace />} />
            </Route>
          </Routes>
        </StoreProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
