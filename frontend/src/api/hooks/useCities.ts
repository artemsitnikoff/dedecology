import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

/**
 * GET /incidents/cities — DISTINCT непустые значения Incident.city,
 * отсортированные по алфавиту (А→Я). Нужен для дропдауна фильтра города.
 * Если передан region — только города этого региона.
 */
export async function getCities(region?: string): Promise<string[]> {
  const params = new URLSearchParams();
  if (region) params.set('region', region);
  const qs = params.toString();
  const res = await api.get<string[]>(`/incidents/cities${qs ? `?${qs}` : ''}`);
  return res.data;
}

/**
 * Список городов для фильтра. Зависит от выбранного региона: region входит в
 * queryKey, поэтому смена региона перезапрашивает свой список городов.
 * Меняется редко → большой staleTime, чтобы не дёргать сеть на каждом заходе.
 */
export function useCities(region?: string) {
  return useQuery({
    queryKey: ['incidents', 'cities', region || null],
    queryFn: () => getCities(region),
    staleTime: 30 * 60 * 1000, // 30 минут — справочник почти статичен
  });
}
