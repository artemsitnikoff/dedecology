import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentListItem, Paginated, Source, Status } from '@/api/aliases';

/** Ключ сортировки таблицы (совпадает с контрактом GET /incidents §3). */
export type SortKey = 'date' | 'time' | 'region' | 'city' | 'address' | 'status' | 'source';
/** Направление сортировки. */
export type SortOrder = 'asc' | 'desc';

/**
 * Фильтры списка инцидентов — единый объект, который живёт в URL и является
 * частью queryKey. Поля совпадают с query-параметрами GET /incidents.
 */
export interface IncidentFilters {
  search?: string;
  /** Множественный выбор источника (max/form). */
  source?: Source[];
  /** Одиночный регион — точное совпадение по Incident.region. */
  region?: string;
  /** Одиночный тип инцидента — код (см. IncidentType); точное совпадение по Incident.incident_type. */
  incident_type?: string;
  /** Одиночный статус из воронки. */
  status?: Status;
  date_from?: string;
  date_to?: string;
  sort?: SortKey;
  order?: SortOrder;
  page?: number;
  page_size?: number;
}

/**
 * Собирает URLSearchParams из объекта фильтров. Пустые значения пропускаются;
 * массив source добавляется повторяющимися ключами (?source=max&source=form).
 * Экспортируется, чтобы выгрузка использовала ту же сборку, что и список.
 */
export function buildIncidentParams(filters: IncidentFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.source?.length) {
    for (const s of filters.source) params.append('source', s);
  }
  if (filters.region) params.set('region', filters.region);
  if (filters.incident_type) params.set('incident_type', filters.incident_type);
  if (filters.status) params.set('status', filters.status);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.order) params.set('order', filters.order);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));
  return params;
}

/**
 * GET /incidents — пагинированный список строк таблицы.
 * Объект filters входит в queryKey, поэтому смена любого фильтра/сортировки
 * автоматически перезапрашивает данные с правильным кешированием.
 */
export function useIncidents(filters: IncidentFilters) {
  return useQuery({
    queryKey: ['incidents', filters],
    queryFn: async () => {
      const params = buildIncidentParams(filters);
      const res = await api.get<Paginated<IncidentListItem>>(`/incidents?${params.toString()}`);
      return res.data;
    },
  });
}
