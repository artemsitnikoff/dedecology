import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { MnoDetail, MnoListItem, MnoPointsResponse, Paginated } from '@/api/aliases';

/** Ключ сортировки таблицы МНО (сортируемые колонки прототипа). */
export type MnoSortKey = 'reg' | 'name' | 'region' | 'city' | 'address';
/** Направление сортировки. */
export type SortOrder = 'asc' | 'desc';

/**
 * Фильтры списка МНО — часть queryKey. Поля совпадают с query-параметрами GET /mno
 * (контракт: region(code)/synced(bool)/search/sort/order + пагинация page/page_size).
 * Фильтрация/сортировка/пагинация — серверные (как у incidents).
 */
export interface MnoFilters {
  search?: string;
  /** Код региона (Region.code). */
  region?: string;
  /** Только синхронизированные (true) / только вручную (false); undefined — все. */
  synced?: boolean;
  sort?: MnoSortKey;
  order?: SortOrder;
  /** Номер страницы (1-based). Не задан → сервер отдаёт первую. */
  page?: number;
  /** Размер страницы (по контракту 1..200). */
  page_size?: number;
}

/**
 * Собирает URLSearchParams из фильтров МНО. Пустые значения пропускаются.
 * Экспортируется, чтобы выгрузка реестра использовала ту же сборку, что и список.
 * ВНИМАНИЕ: page/page_size добавляются только если заданы — выгрузка (весь набор)
 * их не передаёт, поэтому экспорт остаётся полным.
 */
export function buildMnoParams(filters: MnoFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.region) params.set('region', filters.region);
  if (typeof filters.synced === 'boolean') params.set('synced', String(filters.synced));
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));
  return params;
}

/**
 * GET /mno — пагинированный список МНО. Объект filters входит в queryKey (включая
 * page/page_size), поэтому смена любого фильтра/сортировки/страницы перезапрашивает
 * данные с корректным кешированием (как useIncidents).
 */
export function useMno(filters: MnoFilters) {
  return useQuery({
    queryKey: ['mno', filters],
    queryFn: async () => {
      const params = buildMnoParams(filters);
      const qs = params.toString();
      const res = await api.get<Paginated<MnoListItem>>(`/mno${qs ? `?${qs}` : ''}`);
      return res.data;
    },
  });
}

/**
 * GET /mno/points — лёгкие координаты МНО для карты (без пагинации; сервер обрезает
 * до лимита и сообщает capped/total). Принимает только search/region/synced — БЕЗ
 * page/sort. Карта не грузит полный реестр, поэтому это отдельный запрос.
 */
export function useMnoPoints(
  filters: Pick<MnoFilters, 'search' | 'region' | 'synced'>,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['mno', 'points', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.search?.trim()) params.set('search', filters.search.trim());
      if (filters.region) params.set('region', filters.region);
      if (typeof filters.synced === 'boolean') params.set('synced', String(filters.synced));
      const qs = params.toString();
      const res = await api.get<MnoPointsResponse>(`/mno/points${qs ? `?${qs}` : ''}`);
      return res.data;
    },
    enabled: options?.enabled ?? true,
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
