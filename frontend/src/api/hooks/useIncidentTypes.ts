import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentType } from '@/api/aliases';

/**
 * GET /intake/incident-types — публичный справочник типов инцидента (код + подпись).
 * Роут в intake-группе БЕЗ авторизации, поэтому хук одинаково работает и на публичной
 * форме (аноним), и в админке (по токену). Справочник статичен → большой staleTime,
 * чтобы не дёргать сеть при каждом заходе.
 */
export async function getIncidentTypes(): Promise<IncidentType[]> {
  const res = await api.get<IncidentType[]>('/intake/incident-types');
  return res.data;
}

/**
 * Хук справочника типов инцидента для дропдаунов (форма + фильтр + карточка).
 * queryKey = ['intake','incident-types'] — отдельный от админского ['incident-types'],
 * чтобы CRUD-мутации инвалидировали ОБА кэша (полный список страницы + публичный дропдаун).
 */
export function useIncidentTypes() {
  return useQuery({
    queryKey: ['intake', 'incident-types'],
    queryFn: getIncidentTypes,
    staleTime: 60 * 60 * 1000, // 1 час — справочник почти статичен
  });
}
