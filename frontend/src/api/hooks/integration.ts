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
 * GET /integration/mno/sync/status?region_code=__all__ — последняя задача «Все регионы».
 * Нужен для переподключения к идущей фоновой синхронизации после перезагрузки страницы (F5):
 * бэк-задача серверная и НЕ прерывается, теряется лишь job_id во фронт-состоянии.
 * Нет активной задачи → бэк отвечает 404, и мы возвращаем null (это НЕ ошибка запроса).
 */
export function useRunningAllJob() {
  return useQuery({
    queryKey: ['integration', 'mno', 'running-all'],
    queryFn: async (): Promise<MnoSyncStatus | null> => {
      try {
        const res = await api.get<MnoSyncStatus>(
          '/integration/mno/sync/status?region_code=__all__'
        );
        return res.data;
      } catch {
        return null; // 404 (нет задачи) → null, не ошибка
      }
    },
    staleTime: 0,
  });
}
