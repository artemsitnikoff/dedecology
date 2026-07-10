import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { BlockedDomainCreate, BlockedDomainItem } from '@/api/aliases';

/**
 * POST /blocked-domains — добавить домен в стоп-лист (admin). Бэк нормализует домен
 * (lowercase, срезает «@»); дубль → 409, пустой/без точки → 400.
 */
export function useCreateBlockedDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BlockedDomainCreate) => {
      const res = await api.post<BlockedDomainItem>('/blocked-domains', body);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['blocked-domains'] }),
  });
}

/** DELETE /blocked-domains/{id} — убрать домен из стоп-листа (admin). */
export function useDeleteBlockedDomain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/blocked-domains/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['blocked-domains'] }),
  });
}
