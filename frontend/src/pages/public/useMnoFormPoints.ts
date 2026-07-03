/**
 * Хук точек МНО для модалки выбора на публичной форме (TanStack Query).
 * Оборачивает публичный GET /intake/mno-points по bbox видимого кадра карты.
 *
 * bbox входит в queryKey → смена кадра автоматически перезапрашивает точки.
 * enabled=false, пока bbox не задан (нет кадра) — чтобы не тянуть весь реестр.
 * Внешний `enabled` (напр. «локация ещё не определена») дополнительно гасит запрос.
 * keepPreviousData — карта не мигает пустотой при панораме/зуме.
 */
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchMnoFormPoints } from '@/api/intake';

export function useMnoFormPoints(
  bbox: string | null,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['intake', 'mno-points', bbox],
    queryFn: ({ signal }) => fetchMnoFormPoints(bbox as string, signal),
    enabled: !!bbox && (options?.enabled ?? true),
    placeholderData: keepPreviousData,
  });
}
