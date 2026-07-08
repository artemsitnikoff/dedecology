import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Incident, Status } from '@/api/aliases';

/** PATCH /incidents/{id}/status — смена статуса одного инцидента. */
export function useSetStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Status }) => {
      const res = await api.patch<Incident>(`/incidents/${id}/status`, { status });
      return res.data;
    },
    onSuccess: (data) => {
      // PATCH возвращает свежий инцидент целиком — кладём его в кеш детали,
      // чтобы открытая карточка обновила статус мгновенно (без повторного loading).
      qc.setQueryData(['incident', data.id], data);
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incidents', 'funnel'] });
    },
  });
}

/** POST /incidents/bulk-status — массовая пометка статуса по списку id. */
export function useBulkStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ids, status }: { ids: string[]; status: Status }) => {
      const res = await api.post<{ updated: number }>('/incidents/bulk-status', { ids, status });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incidents', 'funnel'] });
      // Открытая карточка могла попасть в выборку — освежим её детали.
      qc.invalidateQueries({ queryKey: ['incident'] });
    },
  });
}

/** POST /incidents/bulk-delete — массовое удаление по списку id (необратимо). */
export function useBulkDelete() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ids: string[]) => {
      const res = await api.post<{ deleted: number }>('/incidents/bulk-delete', { ids });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incidents', 'funnel'] });
    },
  });
}
