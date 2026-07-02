import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Volunteer } from '@/api/aliases';

/**
 * GET /volunteers — справочник волонтёров мобильного приложения (на бэке под admin-гейтом).
 * Нужен странице-справочнику «Волонтёры» в админке (просмотр + блокировка/удаление).
 * Волонтёры регистрируются сами в мобильном приложении — здесь только их триаж.
 */
export function useVolunteers() {
  return useQuery({
    queryKey: ['volunteers'],
    queryFn: async () => {
      const res = await api.get<Volunteer[]>('/volunteers');
      return res.data;
    },
  });
}
