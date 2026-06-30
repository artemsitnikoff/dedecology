import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { RegionCreate, RegionDetail } from '@/api/aliases';

/** POST /regions — добавить субъект РФ в справочник (active=true). Инвалидирует список. */
export function useCreateRegion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RegionCreate) => {
      const res = await api.post<RegionDetail>('/regions', body);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['regions'] });
    },
  });
}
