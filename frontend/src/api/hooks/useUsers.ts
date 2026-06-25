import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAuthStore } from '@/store/authStore';
import type { UserListItem } from '@/api/aliases';

/**
 * GET /users — список пользователей (роут защищён require_admin на бэке).
 * Включаем запрос только для admin, чтобы у обычного пользователя не было
 * заведомо-403 обращения.
 */
export function useUsers() {
  const role = useAuthStore((s) => s.user?.role);
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get<UserListItem[]>('/users');
      return res.data;
    },
    enabled: role === 'admin',
  });
}
