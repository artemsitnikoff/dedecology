import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { FunnelCounts } from '@/api/aliases';
import type { IncidentFilters } from './useIncidents';

/**
 * GET /incidents/funnel — счётчики воронки.
 * Учитывает search/source/period, но НЕ status (каждый чип показывает своё
 * число-кандидат). queryKey — ['incidents','funnel', subset], чтобы смена
 * статуса не дёргала пересчёт воронки зря.
 */
export function useFunnelCounts(filters: IncidentFilters) {
  // Берём только те поля, что влияют на воронку (без status/sort/order/page).
  const subset = {
    search: filters.search,
    source: filters.source,
    region: filters.region,
    date_from: filters.date_from,
    date_to: filters.date_to,
  };
  return useQuery({
    queryKey: ['incidents', 'funnel', subset],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (subset.search?.trim()) params.set('search', subset.search.trim());
      if (subset.source?.length) {
        for (const s of subset.source) params.append('source', s);
      }
      if (subset.region) params.set('region', subset.region);
      if (subset.date_from) params.set('date_from', subset.date_from);
      if (subset.date_to) params.set('date_to', subset.date_to);
      const res = await api.get<FunnelCounts>(`/incidents/funnel?${params.toString()}`);
      return res.data;
    },
  });
}
