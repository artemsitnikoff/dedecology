import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Role, UserCreateResult } from '@/api/aliases';

/**
 * POST /users — создание приглашённого пользователя.
 * Возвращает temp_password ОДИН раз (письмо не отправляется — фаза позже).
 */
export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ fio, email, role }: { fio: string; email: string; role: Role }) => {
      const res = await api.post<UserCreateResult>('/users', { fio, email, role });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

/** DELETE /users/{id} — удаление пользователя (admin-роли защищены на бэке). */
export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/users/${id}`);
      return id;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
