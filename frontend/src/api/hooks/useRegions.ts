import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

/**
 * GET /incidents/regions — DISTINCT непустые значения Incident.region,
 * отсортированные по алфавиту (А→Я). Нужен для дропдауна фильтра региона.
 */
export async function getRegions(): Promise<string[]> {
  const res = await api.get<string[]>('/incidents/regions');
  return res.data;
}

/**
 * Список регионов для фильтра. Меняется редко → большой staleTime,
 * чтобы не дёргать сеть на каждом заходе на экран.
 */
export function useRegions() {
  return useQuery({
    queryKey: ['incidents', 'regions'],
    queryFn: getRegions,
    staleTime: 30 * 60 * 1000, // 30 минут — справочник почти статичен
  });
}
