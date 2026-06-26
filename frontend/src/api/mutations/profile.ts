import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAuthStore } from '@/store/authStore';
import type { UserMe } from '@/api/aliases';

/**
 * PATCH /profile — смена Заявителя текущего пользователя.
 * При успехе обновляем стор (сайдбар/шапка читают user.fio).
 */
export function useUpdateProfile() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  return useMutation({
    mutationFn: async ({ fio }: { fio: string }) => {
      const res = await api.patch<UserMe>('/profile', { fio });
      return res.data;
    },
    onSuccess: (user) => {
      setUser(user);
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
}

/**
 * POST /profile/password — установка нового пароля (без текущего, ТЗ §9.1).
 */
export function useResetPassword() {
  return useMutation({
    mutationFn: async ({ new_password }: { new_password: string }) => {
      const res = await api.post<{ message: string }>('/profile/password', { new_password });
      return res.data;
    },
  });
}
