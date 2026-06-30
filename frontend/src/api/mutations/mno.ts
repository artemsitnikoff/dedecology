import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { buildMnoParams } from '@/api/hooks/mno';
import type { MnoFilters } from '@/api/hooks/mno';
import type { MnoCreate, MnoDetail, MnoSyncResult } from '@/api/aliases';

/** Имя файла реестра по умолчанию — fallback, если нет Content-Disposition. */
const EXPORT_FILENAME = 'МНО_ЭкоПульс.xlsx';

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

/**
 * GET /mno/export — выгрузка реестра МНО в .xlsx по текущему фильтру (openpyxl на бэке).
 * Контракт даёт только фильтр-экспорт (нет select-by-ids, в отличие от incidents),
 * поэтому выгружается отфильтрованный реестр целиком.
 */
export async function exportMno(filters: MnoFilters): Promise<void> {
  const params = buildMnoParams(filters);
  const qs = params.toString();
  const res = await api.get(`/mno/export${qs ? `?${qs}` : ''}`, { responseType: 'blob' });
  const filename = filenameFromDisposition(
    res.headers['content-disposition'] as string | undefined,
    EXPORT_FILENAME
  );
  triggerDownload(res.data as Blob, filename);
}

/** POST /mno — добавить МНО вручную (synced=false, fgis_id=null). Инвалидирует список. */
export function useCreateMno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: MnoCreate) => {
      const res = await api.post<MnoDetail>('/mno', body);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mno'] });
    },
  });
}

/**
 * POST /mno/sync — ЗАГЛУШКА синхронизации с ФГИС (реальной интеграции нет): помечает
 * все ещё-не-synced МНО synced=true + sync_date + placeholder fgis_id. Это РЕАЛЬНЫЙ
 * вызов бэкенд-заглушки, а не кнопка-пустышка. Возвращает {synced, total}.
 */
export function useSyncMno() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<MnoSyncResult>('/mno/sync');
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['mno'] });
    },
  });
}

/** POST /mno/{id}/sync — заглушка синхронизации одного МНО. Освежает список и деталь. */
export function useSyncMnoOne() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post<MnoDetail>(`/mno/${id}/sync`);
      return res.data;
    },
    onSuccess: (data) => {
      qc.setQueryData(['mno', 'detail', data.id], data);
      qc.invalidateQueries({ queryKey: ['mno'] });
    },
  });
}
