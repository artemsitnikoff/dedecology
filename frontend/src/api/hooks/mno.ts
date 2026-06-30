import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { MnoDetail, MnoListItem } from '@/api/aliases';

/** Ключ сортировки таблицы МНО (сортируемые колонки прототипа). */
export type MnoSortKey = 'reg' | 'name' | 'region' | 'city' | 'address';
/** Направление сортировки. */
export type SortOrder = 'asc' | 'desc';

/**
 * Фильтры списка МНО — часть queryKey. Поля совпадают с query-параметрами GET /mno
 * (контракт: region(code)/synced(bool)/search/sort/order). Фильтрация/сортировка —
 * серверные (как у incidents), список приходит уже готовым.
 */
export interface MnoFilters {
  search?: string;
  /** Код региона (Region.code). */
  region?: string;
  /** Только синхронизированные (true) / только вручную (false); undefined — все. */
  synced?: boolean;
  sort?: MnoSortKey;
  order?: SortOrder;
}

/**
 * Собирает URLSearchParams из фильтров МНО. Пустые значения пропускаются.
 * Экспортируется, чтобы выгрузка реестра использовала ту же сборку, что и список.
 */
export function buildMnoParams(filters: MnoFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.region) params.set('region', filters.region);
  if (typeof filters.synced === 'boolean') params.set('synced', String(filters.synced));
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  return params;
}

/**
 * GET /mno — список МНО (плоский, не пагинированный). Объект filters входит в
 * queryKey, поэтому смена любого фильтра/сортировки перезапрашивает данные.
 */
export function useMno(filters: MnoFilters) {
  return useQuery({
    queryKey: ['mno', filters],
    queryFn: async () => {
      const params = buildMnoParams(filters);
      const qs = params.toString();
      const res = await api.get<MnoListItem[]>(`/mno${qs ? `?${qs}` : ''}`);
      return res.data;
    },
  });
}

/**
 * GET /mno/{id} — деталь МНО для карточки-drawer. queryKey отделён от списка,
 * `enabled` гасит запрос при null id (drawer закрыт). Карточка держит loading из Query.
 */
export function useMnoDetail(id: string | null) {
  return useQuery({
    queryKey: ['mno', 'detail', id],
    queryFn: async () => {
      const res = await api.get<MnoDetail>(`/mno/${id}`);
      return res.data;
    },
    enabled: id != null,
  });
}
