import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Paginated } from '@/api/aliases';

/** Строка списка технических ошибок (GET /errors, только admin). */
export interface ErrorReportItem {
  id: string;
  /** Уникальный код ошибки («ERR-A1B2C3D4»). */
  code: string;
  /** Тип ошибки: «server» | «auth» | «photo_upload» | «other» | свободный. */
  error_type: string;
  /** Понятное описание («Серверная ошибка»); null — нет. */
  message: string | null;
  /** Версия мобильного приложения; null — не передана. */
  app_version: string | null;
  /** Платформа («android»/«ios»); null — не передана. */
  platform: string | null;
  /** Email волонтёра, если известен; null — аноним. */
  volunteer_email: string | null;
  /** ISO — время сбоя на клиенте; null — не передано. */
  occurred_at: string | null;
  /** ISO — момент регистрации на сервере. */
  created_at: string;
  /** Ушло ли письмо в техподдержку (ecopulse@reo.ru). */
  emailed: boolean;
}

/** Полная карточка ошибки (GET /errors/{id}) — поля списка + контекст. */
export interface ErrorReportDetail extends ErrorReportItem {
  /** Действие пользователя перед сбоем; null — не передано. */
  user_action: string | null;
  /** Технические данные (stacktrace/запрос/устройство) — произвольный JSON. */
  technical: Record<string, unknown> | null;
  /** Текст ошибки отправки письма в поддержку; null — письмо ушло/не пробовали. */
  email_error: string | null;
}

/** Тип ошибки → русская подпись (известные типы; иначе — исходный код). */
export const ERROR_TYPE_LABELS: Record<string, string> = {
  server: 'Серверная ошибка',
  auth: 'Ошибка авторизации',
  photo_upload: 'Ошибка загрузки фото',
  network: 'Ошибка сети',
  other: 'Прочая ошибка',
};

/** GET /errors — пагинированный список технических ошибок, свежие сверху (admin). */
export function useErrorReports(page: number, pageSize = 50) {
  return useQuery({
    queryKey: ['errors', { page, pageSize }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (page > 1) params.set('page', String(page));
      if (pageSize) params.set('page_size', String(pageSize));
      const qs = params.toString();
      const res = await api.get<Paginated<ErrorReportItem>>(`/errors${qs ? `?${qs}` : ''}`);
      return res.data;
    },
  });
}

/** GET /errors/{id} — полная карточка ошибки (enabled только когда id задан). */
export function useErrorReport(id: string | null) {
  return useQuery({
    queryKey: ['errors', id],
    enabled: !!id,
    queryFn: async () => {
      const res = await api.get<ErrorReportDetail>(`/errors/${id}`);
      return res.data;
    },
  });
}
