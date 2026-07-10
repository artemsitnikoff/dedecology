import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { IncidentSubtype } from '@/api/aliases';

/** Карта подтипов: код типа инцидента → его подтипы. Подтипы есть только у «no_access». */
export type IncidentSubtypesMap = Record<string, IncidentSubtype[]>;

/**
 * GET /intake/incident-subtypes — публичный справочник подтипов инцидента (фиксированный на
 * бэке: подтип есть только для типа «Отсутствует доступ к МНО»/no_access). БЕЗ авторизации —
 * работает и на публичной форме, и в админке. Почти статичен → большой staleTime.
 */
export async function getIncidentSubtypes(): Promise<IncidentSubtypesMap> {
  const res = await api.get<IncidentSubtypesMap>('/intake/incident-subtypes');
  return res.data;
}

/** Хук карты подтипов инцидента (форма показывает подтип только для типа с подтипами). */
export function useIncidentSubtypes() {
  return useQuery({
    queryKey: ['intake', 'incident-subtypes'],
    queryFn: getIncidentSubtypes,
    staleTime: 60 * 60 * 1000,
  });
}
