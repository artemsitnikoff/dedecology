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

/** Хук справочника типов инцидента для дропдаунов (форма + фильтр + карточка). */
export function useIncidentTypes() {
  return useQuery({
    queryKey: ['incident-types'],
    queryFn: getIncidentTypes,
    staleTime: 60 * 60 * 1000, // 1 час — справочник почти статичен
  });
}
