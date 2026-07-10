import { useEffect, useState, lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuthStore, selectIsAuthenticated } from '@/store/authStore';
import { api } from '@/api/client';
import type { UserMe } from '@/api/aliases';
import AppLayout from '@/components/AppLayout';
import LoginPage from '@/pages/LoginPage';

// Lazy-загружаемые страницы (named exports → .then(m => ({ default: m.X })))
const IncidentsPage = lazy(() =>
  import('@/pages/incidents/IncidentsPage').then((m) => ({ default: m.IncidentsPage }))
);
const SettingsPage = lazy(() =>
  import('@/pages/settings/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);
const MnoPage = lazy(() => import('@/pages/mno/MnoPage').then((m) => ({ default: m.MnoPage })));
const ReportsPage = lazy(() =>
  import('@/pages/reports/ReportsPage').then((m) => ({ default: m.ReportsPage }))
);
const RegionsPage = lazy(() =>
  import('@/pages/regions/RegionsPage').then((m) => ({ default: m.RegionsPage }))
);
const IncidentTypesPage = lazy(() =>
  import('@/pages/incident-types/IncidentTypesPage').then((m) => ({
    default: m.IncidentTypesPage,
  }))
);
const IntegrationPage = lazy(() =>
  import('@/pages/integration/IntegrationPage').then((m) => ({ default: m.IntegrationPage }))
);
const BlockedDomainsPage = lazy(() =>
  import('@/pages/blocked-domains/BlockedDomainsPage').then((m) => ({
    default: m.BlockedDomainsPage,
  }))
);
const VolunteersPage = lazy(() =>
  import('@/pages/volunteers/VolunteersPage').then((m) => ({ default: m.VolunteersPage }))
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage }))
);
// Публичная форма обращения — без авторизации и без сайдбара (sibling /login).
const ReportFormPage = lazy(() => import('@/pages/public/ReportFormPage'));

function RequireAuth({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const setAuth = useAuthStore((s) => s.setAuth);
  const location = useLocation();
  // bootstrap: при первом маунте после reload — token/user в памяти потеряны,
  // но refresh-cookie HttpOnly жива. Пробуем восстановить сессию через refresh.
  const [bootstrapping, setBootstrapping] = useState(!isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      setBootstrapping(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const refresh = await api.post<{ access_token: string }>('/auth/refresh');
        const token = refresh.data.access_token;
        const me = await api.get<UserMe>('/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setAuth(token, me.data);
      } catch {
        // refresh не сработал — пользователь не авторизован, редирект на /login
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, setAuth]);

  if (bootstrapping) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

/**
 * Гард раздела «Интеграция ФГИС» — доступен ТОЛЬКО супер-админу. Не супер-админа
 * (и неавторизованного, у которого user ещё null) уводим на /incidents.
 */
function RequireSuperadmin({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (!user?.is_superadmin) {
    return <Navigate to="/incidents" replace />;
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  if (user?.role !== 'admin') {
    return <Navigate to="/incidents" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/form"
        element={
          <Suspense fallback={null}>
            <ReportFormPage />
          </Suspense>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/incidents" replace />} />
        {/* Splat: /incidents и /incidents/<id> — один элемент → ЧПУ-карточка без ремаунта. */}
        <Route path="incidents/*" element={<IncidentsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        {/* Splat (/*): /mno и /mno/<id> матчит один и тот же элемент → карточка (ЧПУ)
            открывается без ремаунта страницы. Аналогично /mno-new (волонтёрские МНО). */}
        <Route path="mno/*" element={<MnoPage sourceFilter="fgis" />} />
        <Route path="mno-new/*" element={<MnoPage sourceFilter="volunteer" />} />
        <Route path="regions" element={<RegionsPage />} />
        <Route path="incident-types" element={<IncidentTypesPage />} />
        <Route
          path="blocked-domains"
          element={
            <RequireAdmin>
              <BlockedDomainsPage />
            </RequireAdmin>
          }
        />
        <Route path="volunteers" element={<VolunteersPage />} />
        <Route
          path="integration"
          element={
            <RequireSuperadmin>
              <IntegrationPage />
            </RequireSuperadmin>
          }
        />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
