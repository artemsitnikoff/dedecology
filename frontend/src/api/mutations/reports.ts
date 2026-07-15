import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Source, Status } from '@/api/aliases';
import type { ReportListItem } from '@/api/hooks/useReports';

/**
 * Тело POST /reports/incidents. Если ids непуст — отчёт формируется по выбранным
 * строкам, иначе — по текущему фильтру списка инцидентов (см. IncidentsPage).
 */
export interface CreateIncidentsReportBody {
  ids?: string[];
  search?: string;
  source?: Source[];
  status?: Status[];
  region?: string;
  city?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: 'asc' | 'desc';
}

/**
 * POST /reports/incidents — формирует .xlsx-отчёт по обращениям (файл на бэке, в
 * раздел «Отчёты»); прямого скачивания не возвращает. Инвалидирует список отчётов.
 */
export function useCreateIncidentsReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateIncidentsReportBody) => {
      const res = await api.post<ReportListItem>('/reports/incidents', body);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}

/** Достаёт имя файла из Content-Disposition (RFC 5987 `filename*` или обычный `filename`). */
function filenameFromDisposition(disposition: string | undefined, fallback: string): string {
  if (!disposition) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      return fallback;
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  if (plain?.[1]) return plain[1];
  return fallback;
}

/** Сохраняет blob как файл: временный <a download> → click → revoke. */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** GET /reports/{id}/download — скачивает готовый .xlsx-файл отчёта. */
export async function downloadReport(id: string, filename: string): Promise<void> {
  const res = await api.get(`/reports/${id}/download`, { responseType: 'blob' });
  const name = filenameFromDisposition(
    res.headers['content-disposition'] as string | undefined,
    filename
  );
  triggerDownload(res.data as Blob, name);
}

/** DELETE /reports/{id} — удаляет отчёт (и его файл на бэке). Инвалидирует список. */
export function useDeleteReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.delete<{ message: string }>(`/reports/${id}`);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}
