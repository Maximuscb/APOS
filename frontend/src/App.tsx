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
const DashboardPage = lazy(() => import('@/routes/operations/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const DevicesPage = lazy(() => import('@/routes/operations/DevicesPage'));
const ReportsPage = lazy(() => import('@/routes/operations/ReportsPage').then((m) => ({ default: m.ReportsPage })));
const AnalyticsPage = lazy(() => import('@/routes/operations/AnalyticsPage'));
const ServicesPage = lazy(() => import('@/routes/operations/ServicesPage'));
const TimekeepingPage = lazy(() => import('@/routes/operations/TimekeepingPage'));
const UsersPage = lazy(() => import('@/routes/operations/UsersPage'));
const SettingsPage = lazy(() => import('@/routes/operations/SettingsPage'));
const VendorsPage = lazy(() => import('@/routes/operations/VendorsPage'));
const CommunicationsPage = lazy(() => import('@/routes/operations/CommunicationsPage').then((m) => ({ default: m.CommunicationsPage })));
const OrganizationPage = lazy(() => import('@/routes/operations/OrganizationPage').then((m) => ({ default: m.OrganizationPage })));
const PromotionsPage = lazy(() => import('@/routes/operations/PromotionsPage').then((m) => ({ default: m.PromotionsPage })));
const DeveloperPage = lazy(() => import('@/routes/operations/DeveloperPage'));

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
              <Route path="/sales" element={<RegisterPage />} />
              <Route path="/register" element={<Navigate to="/sales" replace />} />
              <Route path="/inventory" element={<InventoryPage />} />

              <Route path="/operations" element={<OperationsLayout />}>
                <Route index element={<Navigate to="/operations/dashboard" replace />} />
                <Route path="dashboard" element={<Suspense fallback={<Loading />}><DashboardPage /></Suspense>} />
                <Route path="devices" element={<Suspense fallback={<Loading />}><DevicesPage /></Suspense>} />
                <Route path="reports" element={<Suspense fallback={<Loading />}><ReportsPage /></Suspense>} />
                <Route path="documents" element={<Navigate to="/operations/reports" replace />} />
                <Route path="analytics" element={<Suspense fallback={<Loading />}><AnalyticsPage /></Suspense>} />
                <Route path="services" element={<Suspense fallback={<Loading />}><ServicesPage /></Suspense>} />
                <Route path="timekeeping" element={<Suspense fallback={<Loading />}><TimekeepingPage /></Suspense>} />
                <Route path="users" element={<Suspense fallback={<Loading />}><UsersPage /></Suspense>} />
                <Route path="vendors" element={<Suspense fallback={<Loading />}><VendorsPage /></Suspense>} />
                <Route path="communications" element={<Suspense fallback={<Loading />}><CommunicationsPage /></Suspense>} />
                <Route path="organization" element={<Suspense fallback={<Loading />}><OrganizationPage /></Suspense>} />
                <Route path="promotions" element={<Suspense fallback={<Loading />}><PromotionsPage /></Suspense>} />
                <Route path="developer" element={<Suspense fallback={<Loading />}><DeveloperPage /></Suspense>} />
                <Route path="settings" element={<Suspense fallback={<Loading />}><SettingsPage /></Suspense>} />
                <Route path="registers" element={<Navigate to="/operations/devices" replace />} />
                <Route path="overrides" element={<Navigate to="/operations/users" replace />} />
                <Route path="imports" element={<Navigate to="/operations/services" replace />} />
                <Route path="audits" element={<Navigate to="/operations/reports" replace />} />
                <Route path="events" element={<Navigate to="/operations/reports" replace />} />
              </Route>

              <Route path="*" element={<Navigate to="/operations/dashboard" replace />} />
            </Route>
          </Routes>
        </StoreProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
