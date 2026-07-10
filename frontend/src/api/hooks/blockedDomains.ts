import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { BlockedDomainItem } from '@/api/aliases';

/**
 * GET /blocked-domains — справочник «Стоп-лист почтовых доменов» (только admin).
 * Регистрация волонтёра с адресом на таком домене блокируется на бэке. Роут admin-only,
 * поэтому хук используется только на одноимённой странице (пункт сайдбара виден админам).
 */
export async function getBlockedDomains(): Promise<BlockedDomainItem[]> {
  const res = await api.get<BlockedDomainItem[]>('/blocked-domains');
  return res.data;
}

/** Список заблокированных доменов для страницы-справочника. queryKey ['blocked-domains']. */
export function useBlockedDomainsList() {
  return useQuery({
    queryKey: ['blocked-domains'],
    queryFn: getBlockedDomains,
  });
}
