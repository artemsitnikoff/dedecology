import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Incident, Status } from '@/api/aliases';
import { buildIncidentParams } from '@/api/hooks/useIncidents';
import type { IncidentFilters } from '@/api/hooks/useIncidents';

/** Имя файла по умолчанию (см. BUILD-SPEC §3) — fallback, если нет Content-Disposition. */
const EXPORT_FILENAME_ALL = 'Инциденты_ДедЭколог.xlsx';
const EXPORT_FILENAME_SELECTED = 'Инциденты_ДедЭколог_выбранные.xlsx';

/**
 * Достаёт имя файла из заголовка Content-Disposition.
 * Поддерживает RFC 5987 `filename*=UTF-8''…` и обычный `filename="…"`.
 * Возвращает fallback, если заголовок отсутствует/не распознан.
 */
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

/**
 * GET /incidents/export — выгрузка всего отфильтрованного набора в .xlsx.
 * Те же параметры, что и у списка (минус пагинация на бэке не важна — экспорт полный).
 */
export async function exportAll(filters: IncidentFilters): Promise<void> {
  const params = buildIncidentParams(filters);
  const res = await api.get(`/incidents/export?${params.toString()}`, { responseType: 'blob' });
  const filename = filenameFromDisposition(
    res.headers['content-disposition'] as string | undefined,
    EXPORT_FILENAME_ALL
  );
  triggerDownload(res.data as Blob, filename);
}

/**
 * POST /incidents/export — выгрузка выбранных строк по списку id в .xlsx.
 */
export async function exportSelected(ids: string[]): Promise<void> {
  const res = await api.post('/incidents/export', { ids }, { responseType: 'blob' });
  const filename = filenameFromDisposition(
    res.headers['content-disposition'] as string | undefined,
    EXPORT_FILENAME_SELECTED
  );
  triggerDownload(res.data as Blob, filename);
}

/** PATCH /incidents/{id}/status — смена статуса одного инцидента. */
export function useSetStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Status }) => {
      const res = await api.patch<Incident>(`/incidents/${id}/status`, { status });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incidents', 'funnel'] });
    },
  });
}

/** POST /incidents/bulk-status — массовая пометка статуса по списку id. */
export function useBulkStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ids, status }: { ids: string[]; status: Status }) => {
      const res = await api.post<{ updated: number }>('/incidents/bulk-status', { ids, status });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] });
      qc.invalidateQueries({ queryKey: ['incidents', 'funnel'] });
    },
  });
}
