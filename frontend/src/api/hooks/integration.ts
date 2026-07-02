import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IntegrationOverview, MnoSyncStatus } from '@/api/aliases';

/**
 * Хуки чтения раздела «Интеграция ФГИС» (только супер-админ).
 * Сводка и статус фоновой синхронизации МНО — серверное состояние через TanStack Query.
 */

/**
 * GET /integration/overview — сводка: итоги по регионам/МНО + построчная сводка по регионам.
 * Инвалидируется после синхронизации регионов и по завершении фоновой синхронизации МНО.
 */
export function useIntegrationOverview() {
  return useQuery({
    queryKey: ['integration', 'overview'],
    queryFn: async () => {
      const res = await api.get<IntegrationOverview>('/integration/overview');
      return res.data;
    },
  });
}

/**
 * GET /integration/mno/sync/status?job_id — статус фоновой задачи синхронизации МНО.
 * Опрос ~1500мс, ПОКА state==='running' (опрос гасится сам на done/error); при null jobId
 * запрос выключен. Прогресс (discovered/fetched/upserted) держит Query, не локальный state.
 */
export function useMnoSyncStatus(jobId: string | null) {
  return useQuery({
    queryKey: ['integration', 'mno-sync', jobId],
    queryFn: async () => {
      const res = await api.get<MnoSyncStatus>(
        `/integration/mno/sync/status?job_id=${encodeURIComponent(jobId ?? '')}`
      );
      return res.data;
    },
    enabled: jobId != null,
    // Пока задача выполняется — перезапрашиваем; на done/error интервал выключается.
    refetchInterval: (query) => (query.state.data?.state === 'running' ? 1500 : false),
  });
}

/**
 * GET /integration/mno/sync/active — ЛЮБАЯ идущая фоновая синхронизация (регион ИЛИ «все»).
 * Нужен для переподключения к ней после перезагрузки страницы (F5): бэк-задача серверная и
 * НЕ прерывается, теряется лишь job_id во фронт-состоянии. Раньше подхватывался только прогон
 * «Все регионы», а синк одного региона терялся → UI предлагал запуск заново. Нет активной
 * задачи → бэк отвечает null (это НЕ ошибка).
 */
export function useRunningAnyJob() {
  return useQuery({
    queryKey: ['integration', 'mno', 'running-any'],
    queryFn: async (): Promise<MnoSyncStatus | null> => {
      const res = await api.get<MnoSyncStatus | null>('/integration/mno/sync/active');
      return res.data ?? null;
    },
    staleTime: 0,
  });
}
