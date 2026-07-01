import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { MnoSyncJob, RegionsSyncResult, MnoCancelResult } from '@/api/aliases';

/**
 * Мутации раздела «Интеграция ФГИС» (только супер-админ).
 * Реальные вызовы бэка (POST), а не кнопки-пустышки: синхронизация регионов —
 * синхронная, синхронизация МНО — запуск фоновой задачи (job_id → опрос статуса).
 */

/**
 * POST /integration/regions/sync — синхронная синхронизация справочника субъектов РФ
 * из ФГИС. Инвалидирует сводку интеграции и справочник регионов (счётчики/даты).
 */
export function useSyncRegions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<RegionsSyncResult>('/integration/regions/sync');
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['integration', 'overview'] });
      qc.invalidateQueries({ queryKey: ['regions'] });
    },
  });
}

/**
 * POST /integration/mno/sync {region_code} — запуск ФОНОВОЙ синхронизации МНО региона.
 * Возвращает job_id; прогресс/итог тянутся отдельно через useMnoSyncStatus(job_id).
 * Инвалидация сводки/реестра МНО — по ЗАВЕРШЕНИЮ задачи (на стороне страницы), не здесь.
 */
export function useStartMnoSync() {
  return useMutation({
    mutationFn: async (regionCode: string) => {
      const res = await api.post<MnoSyncJob>('/integration/mno/sync', {
        region_code: regionCode,
      });
      return res.data;
    },
  });
}

/**
 * POST /integration/mno/sync-all — запуск ОДНОЙ фоновой задачи, обходящей ВСЕ регионы
 * справочника последовательно (общий прогресс). Тела нет; возвращает job_id, который
 * опрашивается тем же useMnoSyncStatus(job_id). Инвалидация — по завершении (на странице).
 */
export function useStartMnoSyncAll() {
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<MnoSyncJob>('/integration/mno/sync-all');
      return res.data;
    },
  });
}

/**
 * POST /integration/mno/sync/cancel {scope:'all'} — отмена фоновой синхронизации МНО.
 * Бэк выставляет флаг отмены (задача корректно останавливается в пределах ближайшего
 * батча) и снимает указатель `mno:ptr:__all__` → get_running_job=None, кнопка запуска
 * снова активна. Сброс локального jobId + инвалидация (running-all/overview) — на
 * стороне страницы (в onSuccess вызова), чтобы UI сразу разблокировался.
 */
export function useCancelMnoSync() {
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<MnoCancelResult>('/integration/mno/sync/cancel', {
        scope: 'all',
      });
      return res.data;
    },
  });
}
