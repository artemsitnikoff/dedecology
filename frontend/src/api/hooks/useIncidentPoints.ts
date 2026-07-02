import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentPointsResponse } from '@/api/aliases';
import { buildIncidentParams } from './useIncidents';
import type { IncidentFilters } from './useIncidents';

/**
 * GET /incidents/points — лёгкие координаты инцидентов для карты (без пагинации;
 * сервер обрезает до лимита и сообщает capped/total). Использует те же фильтры, что
 * и список (search/source/status/region/period), но sort/page карте не нужны — их
 * отбрасываем (бэк их всё равно игнорирует). Карта не грузит полный реестр — это
 * отдельный запрос, включаемый только в режиме «Карта» (options.enabled).
 *
 * bbox («minLat,minLon,maxLat,maxLon») — видимая область карты: сервер отдаёт точки
 * только текущего кадра (кап на кадр), так постепенно виден весь регион. bbox входит
 * в queryKey → смена кадра автоматически перезапрашивает точки.
 */
export function useIncidentPoints(
  filters: IncidentFilters & { bbox?: string },
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['incidents', 'points', filters],
    queryFn: async () => {
      const params = buildIncidentParams(filters);
      params.delete('sort');
      params.delete('order');
      params.delete('page');
      params.delete('page_size');
      if (filters.bbox) params.set('bbox', filters.bbox);
      const qs = params.toString();
      const res = await api.get<IncidentPointsResponse>(
        `/incidents/points${qs ? `?${qs}` : ''}`
      );
      return res.data;
    },
    // Держим прошлые точки при смене bbox — карта не мигает пустотой на рефетче.
    placeholderData: keepPreviousData,
    enabled: options?.enabled ?? true,
  });
}
