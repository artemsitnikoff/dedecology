import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentTypeCreate, IncidentTypeItem, IncidentTypeUpdate } from '@/api/aliases';

/**
 * Инвалидируем ОБА кэша справочника типов инцидента:
 *  - ['incident-types']            — полный список страницы админки (useIncidentTypesList);
 *  - ['intake','incident-types']   — публичный дропдаун формы/фильтра/карточки (useIncidentTypes).
 * Так любое CRUD-изменение сразу отражается и в управлении, и в приёме обращений.
 */
function invalidateIncidentTypes(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ['incident-types'] });
  qc.invalidateQueries({ queryKey: ['intake', 'incident-types'] });
}

/** POST /incident-types — создать тип. code/sort_order необязательны (бэк проставит сам). */
export function useCreateIncidentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: IncidentTypeCreate) => {
      const res = await api.post<IncidentTypeItem>('/incident-types', body);
      return res.data;
    },
    onSuccess: () => invalidateIncidentTypes(qc),
  });
}

/** PATCH /incident-types/{id} — изменить подпись/порядок (code не меняется). */
export function useUpdateIncidentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: IncidentTypeUpdate }) => {
      const res = await api.patch<IncidentTypeItem>(`/incident-types/${id}`, body);
      return res.data;
    },
    onSuccess: () => invalidateIncidentTypes(qc),
  });
}

/** DELETE /incident-types/{id} — удалить тип (инциденты с этим кодом остаются, покажут «—»). */
export function useDeleteIncidentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/incident-types/${id}`);
    },
    onSuccess: () => invalidateIncidentTypes(qc),
  });
}
