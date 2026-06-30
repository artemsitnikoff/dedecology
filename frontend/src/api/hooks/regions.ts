import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { FederalDistrict, RegionDetail, RegionListItem } from '@/api/aliases';
import type { SortOrder } from '@/api/hooks/mno';

/**
 * Справочник «Регионы» (субъекты РФ). Имя `useRegions` уже занято хуком
 * фильтра инцидентов (`@/api/hooks/useRegions` → string[] имён из /incidents/regions),
 * поэтому хук списка справочника называется `useRegionsDirectory` — чтобы не путать
 * два разных эндпоинта и не ломать экран «Инциденты».
 */

/** Ключ сортировки таблицы регионов (сортируемые колонки прототипа). */
export type RegionSortKey = 'code' | 'name' | 'fed' | 'operator' | 'mno' | 'inc';

/** Фильтры справочника регионов — часть queryKey (GET /regions: search/sort/order/fed). */
export interface RegionFilters {
  search?: string;
  /** id федерального округа. */
  fed?: number;
  sort?: RegionSortKey;
  order?: SortOrder;
}

/** Собирает query-параметры справочника регионов. */
export function buildRegionParams(filters: RegionFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (typeof filters.fed === 'number') params.set('fed', String(filters.fed));
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  return params;
}

/**
 * GET /regions — справочник субъектов РФ (плоский список). Используется таблицей
 * «Регионы», а также дропдауном фильтра региона на экране МНО и select'ами в модалках.
 */
export function useRegionsDirectory(filters: RegionFilters) {
  return useQuery({
    queryKey: ['regions', filters],
    queryFn: async () => {
      const params = buildRegionParams(filters);
      const qs = params.toString();
      const res = await api.get<RegionListItem[]>(`/regions${qs ? `?${qs}` : ''}`);
      return res.data;
    },
  });
}

/** GET /regions/{code} — деталь региона для карточки-drawer. */
export function useRegionDetail(code: string | null) {
  return useQuery({
    queryKey: ['regions', 'detail', code],
    queryFn: async () => {
      const res = await api.get<RegionDetail>(`/regions/${code}`);
      return res.data;
    },
    enabled: code != null,
  });
}

/**
 * GET /federal-districts — справочник федеральных округов (8 шт). Меняется почти
 * никогда → большой staleTime. Нужен для select'а округа в модалке добавления региона.
 */
export function useFederalDistricts() {
  return useQuery({
    queryKey: ['federal-districts'],
    queryFn: async () => {
      const res = await api.get<FederalDistrict[]>('/federal-districts');
      return res.data;
    },
    staleTime: 60 * 60 * 1000, // 1 час — справочник статичен
  });
}
