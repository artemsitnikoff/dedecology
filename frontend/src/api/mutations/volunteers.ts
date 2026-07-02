import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Volunteer } from '@/api/aliases';

/**
 * PATCH /volunteers/{id}/active — блокировка/разблокировка волонтёра (флаг is_active).
 * Заблокированный волонтёр не может войти в мобильное приложение (403 BLOCKED на login).
 */
export function useSetVolunteerActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const res = await api.patch<Volunteer>(`/volunteers/${id}/active`, { is_active });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['volunteers'] });
    },
  });
}

/** DELETE /volunteers/{id} — удаление волонтёра из справочника. */
export function useDeleteVolunteer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/volunteers/${id}`);
      return id;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['volunteers'] });
    },
  });
}
