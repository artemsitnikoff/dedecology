import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Paginated } from '@/api/aliases';

/**
 * Строка списка сформированных отчётов (GET /reports, POST /reports/incidents).
 * kind — тип отчёта («incidents» — обращения; подпись резолвится на фронте).
 */
export interface ReportListItem {
  id: string;
  kind: string;
  filename: string;
  /** Число строк данных в файле (без учёта шапки). */
  row_count: number;
  size_bytes: number;
  /** ФИО сформировавшего отчёт пользователя; пусто — не определён. */
  created_by_fio: string;
  /** ISO-строка — момент формирования отчёта. */
  created_at: string;
}

/** Параметры серверной пагинации GET /reports. */
export interface ReportsQuery {
  page?: number;
  page_size?: number;
}

/** GET /reports — пагинированная история сформированных отчётов, свежие сверху. */
export function useReports({ page, page_size }: ReportsQuery) {
  return useQuery({
    queryKey: ['reports', { page, page_size }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (page) params.set('page', String(page));
      if (page_size) params.set('page_size', String(page_size));
      const qs = params.toString();
      const res = await api.get<Paginated<ReportListItem>>(`/reports${qs ? `?${qs}` : ''}`);
      return res.data;
    },
  });
}
