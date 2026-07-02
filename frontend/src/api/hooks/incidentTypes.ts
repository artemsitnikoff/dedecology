import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentTypeItem } from '@/api/aliases';

/**
 * GET /incident-types — ПОЛНЫЙ справочник типов инцидента (id/code/label/sort_order),
 * источник правды — таблица incident_types в БД. Нужен странице-справочнику «Типы
 * инцидентов» в админке (таблица + CRUD).
 *
 * Публичный усечённый дропдаун формы/фильтра/карточки берёт /intake/incident-types
 * (см. useIncidentTypes) — здесь именно полный список для управления.
 */
export function useIncidentTypesList() {
  return useQuery({
    queryKey: ['incident-types'],
    queryFn: async () => {
      const res = await api.get<IncidentTypeItem[]>('/incident-types');
      return res.data;
    },
  });
}
