import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import type { Role } from '@/api/aliases';

interface RoleGuardProps {
  children: ReactNode;
  roles: Role[];
  fallbackPath?: string;
}

/**
 * Защита роутов по ролям. Если у пользователя нет нужной роли — редирект на fallbackPath.
 * (Блок «Пользователи» в Настройках admin-only внутри страницы, а не на уровне роута.)
 */
export function RoleGuard({ children, roles, fallbackPath = '/incidents' }: RoleGuardProps) {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!user?.role || !roles.includes(user.role)) {
    return <Navigate to={fallbackPath} state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
