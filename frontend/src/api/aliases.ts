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

/**
 * Запись справочника типов инцидента (GET /intake/incident-types) — код + русская
 * подпись. В инциденте хранится КОД (Incident.incident_type); подпись фронт резолвит
 * по этому справочнику (как federal_districts). Публичный — доступен и на форме без auth.
 */
export interface IncidentType {
  /** Стабильный код типа («fire», «overflow», …). */
  code: string;
  /** Русская подпись для UI («Возгорание в контейнере»). */
  label: string;
}

/**
 * Полная запись справочника типов инцидента (GET /incident-types) — с id и порядком
 * сортировки. Используется страницей-справочником «Типы инцидентов» в админке (CRUD).
 * Источник правды — таблица incident_types в БД (заменила хардкод-константу).
 */
export interface IncidentTypeItem {
  id: string;
  /** Стабильный код типа — на него ссылаются инциденты, при правке НЕ меняется. */
  code: string;
  /** Русская подпись для UI. */
  label: string;
  /** Порядок сортировки в дропдаунах/таблице (меньше — выше). */
  sort_order: number;
}

/**
 * Тело создания типа инцидента (POST /incident-types). Обязателен только label:
 * если code пуст — бэк генерирует стабильный код; если sort_order пуст — ставит в конец.
 */
export interface IncidentTypeCreate {
  label: string;
  code?: string;
  sort_order?: number;
}

/**
 * Тело изменения типа инцидента (PATCH /incident-types/{id}). code менять нельзя
 * (на него ссылаются инциденты) — правим только подпись и порядок.
 */
export interface IncidentTypeUpdate {
  label?: string;
  sort_order?: number;
}

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
  /** Код типа инцидента (см. IncidentType); null — тип не задан. Подпись резолвим по справочнику. */
  incident_type: string | null;
  /** Форма «баки раздельного сбора»; null для Макса. Скрыто в таблице (ТЗ §11), есть в модели. */
  bins: boolean | null;
  /** Реестровый № выбранного на карте МНО (форма); null — МНО не выбирали. */
  mno_reg: string | null;
  /** UUID выбранного на карте МНО (ссылка на объект ТКО); null — МНО не выбирали. */
  mno_id: string | null;
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
  /** Код типа инцидента (см. IncidentType); null — тип не задан. Подпись резолвим по справочнику. */
  incident_type: string | null;
  /** Реестровый № выбранного на карте МНО (форма); null — МНО не выбирали. */
  mno_reg: string | null;
  /** UUID выбранного на карте МНО (ссылка на объект ТКО); null — МНО не выбирали. */
  mno_id: string | null;
  received_at: string;
}

/**
 * Лёгкая точка инцидента для карты (GET /incidents/points) — id + координаты
 * «lat, lon» текстом + статус + краткий адрес (город, улица). Без фото/пагинации.
 */
export interface IncidentPoint {
  id: string;
  coords: string;
  status: Status;
  address: string;
}

/**
 * Ответ GET /incidents/points — координаты инцидентов для карты (без пагинации).
 * total — число инцидентов с непустыми координатами по фильтру; points — первые не
 * более лимита точек; capped=true — точки обрезаны по лимиту (показано меньше total).
 */
export interface IncidentPointsResponse {
  points: IncidentPoint[];
  total: number;
  capped: boolean;
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

/**
 * Волонтёр мобильного приложения — ОТДЕЛЬНАЯ сущность, НЕ пользователь админки
 * (своя таблица volunteers, свой JWT, свои /volunteer/* эндпоинты для приложения).
 * В админке доступен только справочник «Волонтёры» (GET /volunteers, admin-гейт):
 * просмотр + блокировка (is_active) / удаление.
 */
export interface Volunteer {
  id: string;
  /** Email — уникальный, подтверждается по ссылке из письма. */
  email: string;
  /** Телефон — необязательный (проставляется при онбординге в приложении); null — не задан. */
  phone: string | null;
  /** Подтверждён ли email волонтёром (переход по ссылке verify). */
  email_verified: boolean;
  /** Блокировка: false — волонтёр заблокирован и не может войти в приложение. */
  is_active: boolean;
  /** ISO-строка — последняя авторизация (последний запрос волонтёра по JWT / успешный логин); null — ещё ни разу. */
  last_seen_at: string | null;
  /** ISO-строка — момент регистрации. */
  created_at: string;
}

/**
 * Результат админского сброса пароля волонтёра (POST /volunteers/{id}/reset-password).
 * Админ инициирует сброс ПО ID волонтёра (пароль напрямую НЕ меняется): бэк генерит
 * reset-токен и шлёт волонтёру письмо со ссылкой. reset_token/reset_url возвращаются
 * ТОЛЬКО когда письмо не ушло (email_sent=false, SMTP не настроен) — чтобы админ мог
 * честно передать ссылку волонтёру вручную. Без фейка «письмо отправлено».
 */
export interface VolunteerAdminResetResult {
  ok: boolean;
  /** Email волонтёра, которому адресован сброс. */
  email: string;
  /** true — письмо со ссылкой ушло волонтёру; false — SMTP не настроен, письмо НЕ отправлено. */
  email_sent: boolean;
  /** Reset-токен — присутствует только при email_sent=false (для ручной передачи). */
  reset_token?: string | null;
  /** Готовый URL сброса (со встроенным токеном) — только при email_sent=false. */
  reset_url?: string | null;
}

/* ============================================================
   МНО (места накопления отходов) и Регионы (справочник субъектов РФ).
   Заглушки интеграций ФГИС/карт — данные реальные (сиды на бэке), интеграции нет.
   ============================================================ */

/** Федеральный округ (справочник GET /federal-districts, нумерация ФГИС). */
export interface FederalDistrict {
  /** Числовой id округа (1..8 по контракту). */
  id: number;
  /** Краткий код («ЦФО», «СЗФО», …). */
  code: string;
  /** Полное название («Центральный», «Северо-Западный», …). */
  name: string;
}

/** Строка списка МНО (GET /mno) и деталь (GET /mno/{id}) — поля совпадают. */
export interface MnoListItem {
  id: string;
  /** Реестровый № («63-04-001162»). */
  reg: string;
  name: string;
  /** Код субъекта РФ (= Region.code, напр. «63»). */
  region_code: string;
  /** Имя субъекта РФ (резолвится бэком по region_code). */
  region_name: string;
  city: string;
  address: string;
  /** «широта, долгота» текстом. */
  coords: string;
  /** ID в ФГИС; null/пусто — добавлено вручную, ещё не синхронизировано. */
  fgis_id: string | null;
  /** Синхронизировано ли с ФГИС. */
  synced: boolean;
  /** ISO-дата синхронизации или null. */
  sync_date: string | null;
  /** Кол-во обращений по МНО (сидовое/хранимое значение). */
  incidents: number;
}

/** Деталь МНО (GET /mno/{id}) — те же поля, что и в списке. */
export type MnoDetail = MnoListItem;

/** Лёгкая точка МНО для карты (GET /mno/points) — только id + координаты + название. */
export interface MnoPoint {
  id: string;
  /** «широта, долгота» текстом. */
  coords: string;
  name: string;
}

/**
 * Ответ GET /mno/points — координаты МНО для карты (без пагинации).
 * total — всего МНО по фильтру; points — первые не более лимита точек;
 * capped=true — точки обрезаны по лимиту (показано меньше, чем total).
 */
export interface MnoPointsResponse {
  points: MnoPoint[];
  total: number;
  capped: boolean;
}

/**
 * Точка МНО для ПУБЛИЧНОЙ формы (GET /intake/mno-points) — без auth. Помимо
 * координат/названия несёт reg+address: их модалка выбора подставляет в форму
 * (улица = address, рег-номер = reg) при клике по точке.
 */
export interface MnoFormPoint {
  id: string;
  /** «широта, долгота» текстом. */
  coords: string;
  /** Реестровый № МНО (уходит в форму, показывается чипом). */
  reg: string;
  /** Адрес МНО (подставляется в поле «Улица, дом»). */
  address: string;
  name: string;
  /** Имя субъекта РФ (подставляется в поле «Регион»). */
  region: string;
  /** Город/н.п. (подставляется в поле «Город»). */
  city: string;
}

/**
 * Ответ GET /intake/mno-points — точки МНО текущего кадра карты (публичный).
 * total — всего МНО в кадре по bbox; points — первые не более лимита;
 * capped=true — точки обрезаны по лимиту (показано меньше, чем total).
 */
export interface MnoPointsPublicResponse {
  points: MnoFormPoint[];
  total: number;
  capped: boolean;
}

/** Тело создания МНО (POST /mno). Обязательны name+coords; synced=false, fgis_id=null. */
export interface MnoCreate {
  name: string;
  reg: string;
  region_code: string;
  city: string;
  address: string;
  coords: string;
}

/** Результат заглушки синхронизации (POST /mno/sync). */
export interface MnoSyncResult {
  /** Сколько МНО помечено synced в этом вызове. */
  synced: number;
  /** Всего МНО в реестре. */
  total: number;
}

/** Строка списка регионов (GET /regions) и деталь (GET /regions/{code}). */
export interface RegionListItem {
  /** Код субъекта (= regionId ФГИС, напр. «63»). */
  code: string;
  name: string;
  /** id федерального округа. */
  fed: number;
  /** Краткий код округа («ПФО»). */
  fed_code: string;
  /** Название округа («Приволжский»). */
  fed_name: string;
  /** Региональные операторы по ТКО (несколько). */
  operators: string[];
  active: boolean;
  /** ISO-дата последней синхронизации или null. */
  last_sync: string | null;
  /** Число МНО региона. */
  mno_count: number;
  /** Число обращений (Incident.region == Region.name). */
  incidents_count: number;
}

/** Деталь региона (GET /regions/{code}) — те же поля. */
export type RegionDetail = RegionListItem;

/** Тело создания региона (POST /regions). Создаётся active=true. */
export interface RegionCreate {
  code: string;
  name: string;
  fed: number;
  operators: string[];
}

/* ============================================================
   Интеграция ФГИС (раздел супер-админа, /api/v1/integration).
   Живые данные из ФГИС УТКО (public-api.utko.mnr.gov.ru), слой 5 — МНО.
   Типы строго по формам ответов бэка.
   ============================================================ */

/** Строка сводки по региону в разделе интеграции (GET /integration/overview → per_region). */
export interface IntegrationRegionRow {
  /** Код субъекта РФ (regionId ФГИС, напр. «51»). */
  code: string;
  name: string;
  /** id федерального округа (1..8; 0 — неизвестный). */
  fed: number;
  /** Число МНО региона в базе. */
  mno_count: number;
  /** ISO-дата последней синхронизации региона или null. */
  last_sync: string | null;
}

/** Сводка раздела «Интеграция ФГИС» (GET /integration/overview). */
export interface IntegrationOverview {
  regions: {
    /** Всего субъектов РФ в справочнике. */
    total: number;
    /** max(Region.last_sync) — ISO или null. */
    last_sync: string | null;
  };
  mno: {
    /** Всего МНО в базе. */
    total: number;
  };
  per_region: IntegrationRegionRow[];
}

/** Результат синхронизации справочника регионов (POST /integration/regions/sync). */
export interface RegionsSyncResult {
  total: number;
  created: number;
  updated: number;
  /** ISO-момент синхронизации. */
  last_sync: string;
}

/** Состояние фоновой задачи синхронизации МНО ('cancelled' — отменена из UI). */
export type MnoSyncState = 'running' | 'done' | 'error' | 'cancelled' | 'interrupted';

/** Ответ на запуск фоновой синхронизации МНО (POST /integration/mno/sync). */
export interface MnoSyncJob {
  /** UUID фоновой задачи (in-memory реестр бэка; теряется при рестарте). */
  job_id: string;
  region_code: string;
  state: MnoSyncState;
}

/** Статус фоновой синхронизации МНО (GET /integration/mno/sync/status). */
export interface MnoSyncStatus {
  job_id: string;
  region_code: string;
  region_name: string;
  state: MnoSyncState;
  /** Обнаружено id МНО краулером карты (накопительно по всем регионам при scope==='all'). */
  discovered: number;
  /** Загружено деталей (POST sidebar/cluster); накопительно при scope==='all'. */
  fetched: number;
  /** Записано (upsert) в таблицу mno; накопительно при scope==='all'. */
  upserted: number;
  /** Пропущено (уже были в БД, детали не тянулись заново); накопительно. */
  skipped: number;
  /** Текст ошибки при state==='error', иначе null. */
  error: string | null;
  /** ISO-момент старта. */
  started_at: string;
  /** ISO-момент завершения или null (пока running). */
  finished_at: string | null;
  /** Область задачи: один регион ('region', деф.) или весь справочник ('all'). */
  scope: 'region' | 'all';
  /** Всего регионов в обходе (1 для одиночной задачи). */
  regions_total: number;
  /** Регионов успешно пройдено. */
  regions_done: number;
  /** Регионов, завершившихся с ошибкой (сбой одного не роняет весь прогон). */
  regions_failed: number;
  /** Имя региона, обрабатываемого сейчас (для scope==='all'). */
  current_region: string;
  /** Heartbeat: ISO-момент последнего обновления. Если running, но давно не двигался —
   *  задача зависла, UI сам разлочивает запуск (см. IntegrationPage). */
  updated_at: string | null;
}

/**
 * Результат отмены фоновой синхронизации МНО (POST /integration/mno/sync/cancel).
 * Бэк снимает указатель задачи (get_running_job → None) и выставляет флаг отмены.
 */
export interface MnoCancelResult {
  /** true — была активная задача, она отменена; false — активной задачи не было. */
  cancelled: boolean;
  /** job_id отменённой задачи или null (если отменять было нечего). */
  job_id: string | null;
}

/** Конверт ошибки API: { error: { code, message, details } }. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Array<{ field?: string; message: string }> | null;
  };
}
