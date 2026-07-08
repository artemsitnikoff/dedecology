import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { SmtpStatus } from '../hooks/useSmtp';

/** Тело POST /settings/smtp/config — пустой password означает «не менять». */
export interface SmtpConfigRequest {
  host: string;
  port: number;
  encryption: 'tls' | 'ssl' | 'none';
  username: string;
  password: string;
  from_email: string;
  from_name: string;
}

/** Результат POST /settings/smtp/test. */
export interface SmtpTestResult {
  sent_to: string;
  last_test_at: string;
}

/** POST /settings/smtp/config — сохранение параметров SMTP-сервера. */
export function useSmtpSaveConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: SmtpConfigRequest): Promise<SmtpStatus> => {
      const res = await api.post('/settings/smtp/config', data);
      return res.data as SmtpStatus;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'smtp'] });
    },
  });
}

/** POST /settings/smtp/test — отправка тестового письма на указанный адрес. */
export function useSmtpTest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { to: string }): Promise<SmtpTestResult> => {
      const res = await api.post('/settings/smtp/test', data);
      return res.data as SmtpTestResult;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'smtp'] });
    },
  });
}

/** POST /settings/smtp/disconnect — сброс SMTP-настроек. */
export function useSmtpDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<{ message: string }> => {
      const res = await api.post('/settings/smtp/disconnect');
      return res.data as { message: string };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings', 'smtp'] });
    },
  });
}
