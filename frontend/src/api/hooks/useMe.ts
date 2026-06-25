import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAuthStore } from '@/store/authStore';
import type { UserMe } from '@/api/aliases';

/**
 * GET /auth/me — текущий пользователь.
 * Включается только при наличии токена в памяти (после login/bootstrap),
 * чтобы не делать заведомо-401 запрос на старте.
 */
export function useMe() {
  const token = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await api.get<UserMe>('/auth/me');
      return res.data;
    },
    enabled: !!token,
  });
}
