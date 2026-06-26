import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { UserCreate, UserListItem } from '@/api/aliases';

/**
 * POST /users — создание пользователя с ручным паролем.
 * Пользователь создаётся сразу active (без инвайт-флоу), is_superadmin=false.
 * Возвращает созданного пользователя как элемент списка.
 */
export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ fio, email, role, password }: UserCreate) => {
      const res = await api.post<UserListItem>('/users', { fio, email, role, password });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

/**
 * POST /users/{id}/password — ручная установка/сброс пароля пользователю (только admin).
 * Запрещено для супер-админа (бэк отдаёт 403).
 */
export function useSetUserPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, new_password }: { id: string; new_password: string }) => {
      await api.post(`/users/${id}/password`, { new_password });
      return id;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

/** DELETE /users/{id} — удаление пользователя (admin-роли и супер-админ защищены на бэке). */
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
