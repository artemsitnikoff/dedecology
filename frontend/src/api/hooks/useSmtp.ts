import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

/**
 * Статус SMTP-настроек (GET /settings/smtp) — только для admin.
 * Пароль сервер никогда не возвращает (write-only).
 */
export interface SmtpStatus {
  configured: boolean;
  verified: boolean;
  host: string | null;
  port: number | null;
  encryption: 'tls' | 'ssl' | 'none' | null;
  username: string | null;
  from_email: string | null;
  from_name: string | null;
  /** ISO-строка последней проверки тестовым письмом или null — теста ещё не было. */
  last_test_at: string | null;
  last_test_ok: boolean;
  /** Текст ошибки последнего теста; null — либо теста не было, либо прошёл успешно. */
  last_test_error: string | null;
}

/** GET /settings/smtp — текущее состояние почтового сервера. */
export function useSmtpStatus() {
  return useQuery({
    queryKey: ['settings', 'smtp'],
    queryFn: async (): Promise<SmtpStatus> => {
      const res = await api.get('/settings/smtp');
      return res.data as SmtpStatus;
    },
  });
}
