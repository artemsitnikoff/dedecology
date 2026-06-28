/**
 * Доменные типы фронтенда ЭкоПульс — РУЧНАЯ запись, точно по контракту BUILD-SPEC §3.
 *
 * Живого бэкенда для openapi-typescript пока нет, поэтому типы пишем руками.
 * После генерации contracts/openapi.json команда `npm run types:gen` создаст
 * src/api/types.ts — тогда эти алиасы можно переключить на components['schemas'][...].
 * Это единственная точка импорта доменных типов.
 */

/** Источник обращения. */
export type Source = 'max' | 'form';

/** Статус обращения. */
export type Status = 'new' | 'found' | 'none' | 'exported';

/** Роль пользователя. */
export type Role = 'admin' | 'user';

/** Статус пользователя. */
export type UserStatus = 'active' | 'invited';

/** Инцидент (детальное представление, GET /incidents/{id} — все поля, включая bins). */
export interface Incident {
  id: string;
  source: Source;
  status: Status;
  fio: string;
  region: string;
  city: string;
  street: string;
  coords: string;
  /** ISO-строка или null — дата/время фотофиксации. */
  photo_time: string | null;
  photos: number;
  photo_urls: string[];
  /** Макс message id (mid); null для формы. Трейс/поиск, для ссылки НЕ используется. */
  msg: string | null;
  /** Готовый https-URL сообщения Макс (формат https://max.ru/c/{chat_id}/{web_id}); null/пусто — ссылку не показываем. Строится на бэке, на FE больше не собирается. */
  msg_url: string | null;
  /** Прочая не-адресная информация из текста обращения (Радар №…, ФИО заявителя, описание проблемы, заметки); null/пусто — не показываем. */
  comment: string | null;
  /** Форма «баки раздельного сбора»; null для Макса. Скрыто в таблице (ТЗ §11), есть в модели. */
  bins: boolean | null;
  /** ISO-строка — «поступило». */
  received_at: string;
  created_at: string;
  updated_at: string;
}

/** Строка списка инцидентов (GET /incidents). */
export interface IncidentListItem {
  id: string;
  source: Source;
  status: Status;
  fio: string;
  region: string;
  city: string;
  street: string;
  coords: string;
  photo_time: string | null;
  photos: number;
  photo_urls: string[];
  /** Макс message id (mid); null для формы. Трейс/поиск, для ссылки НЕ используется. */
  msg: string | null;
  /** Готовый https-URL сообщения Макс; null/пусто — ссылку не показываем. */
  msg_url: string | null;
  /** Прочая не-адресная инфа (Радар №…, ФИО из текста, описание проблемы). */
  comment: string | null;
  received_at: string;
}

/** Пагинированный ответ. */
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Счётчики воронки (GET /incidents/funnel) — честят search/source/period, НЕ status. */
export interface FunnelCounts {
  all: number;
  new: number;
  found: number;
  none: number;
  exported: number;
}

/** Текущий пользователь (GET /auth/me, PATCH /profile). */
export interface UserMe {
  id: string;
  email: string;
  fio: string;
  role: Role;
  status: UserStatus;
  /** Защищённый супер-админ: нельзя удалить/разжаловать/сбросить пароль чужими руками. */
  is_superadmin: boolean;
}

/** Строка списка пользователей (GET /users). */
export interface UserListItem {
  id: string;
  fio: string;
  email: string;
  role: Role;
  status: UserStatus;
  /** Защищённый супер-админ: нельзя удалить/разжаловать/сбросить пароль чужими руками. */
  is_superadmin: boolean;
}

/** Тело создания пользователя (POST /users) — пароль задаётся вручную, пользователь сразу active. */
export interface UserCreate {
  fio: string;
  email: string;
  role: Role;
  password: string;
}

/** Конверт ошибки API: { error: { code, message, details } }. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Array<{ field?: string; message: string }> | null;
  };
}
