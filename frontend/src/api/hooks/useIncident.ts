import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Incident } from '@/api/aliases';

/**
 * GET /incidents/{id} — детальное представление инцидента (все поля контракта:
 * comment, msg_url, photo_urls, bins и пр.). Используется карточкой DetailDrawer,
 * которая при открытии делает РЕАЛЬНЫЙ запрос и держит loading-состояние из Query.
 *
 * queryKey `['incident', id]` отделён от списка `['incidents', …]`, поэтому
 * инвалидация деталей после смены статуса не задевает список и наоборот.
 * `enabled` гасит запрос при null id (drawer закрыт).
 */
export function useIncident(id: string | null) {
  return useQuery({
    queryKey: ['incident', id],
    queryFn: async () => {
      const res = await api.get<Incident>(`/incidents/${id}`);
      return res.data;
    },
    enabled: id != null,
  });
}
