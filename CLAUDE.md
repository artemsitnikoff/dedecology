# CLAUDE.md — ЭкоПульс

> Читается первым. Админ-панель эколога/инспектора для триажа обращений о состоянии площадок ТКО.
> Построена на стеке и конвенциях соседнего проекта **glafira**. Единый источник правды для
> скаффолда — `docs/BUILD-SPEC.md`; контракт **поведения/вёрстки** — прототип `project/react-app/`
> + ТЗ `project/docs/ТЗ - ЭкоПульс.md`. Скриншоты в `project/screenshots/` — устаревшая
> card-итерация, НЕ ориентир (контракт = исходники прототипа + ТЗ).

---

## 0. Как здесь работают
**ПРАВИЛО: реализацию фич ВЕДЁМ субагентами** `fastapi-expert` (бэк) и `react-expert` (фронт) —
через Agent/Workflow с **обязательным `model` override** (см. грабли #2). Не писать крупные/кросс-
слойные фичи руками: декомпозировать и отдавать этим агентам (кросс-слойные — параллельным Workflow
с единым контрактом backend↔frontend↔maxbot). Напрямую (без агентов) — только мелочь: доки, конфиг,
промпты, деплой, version-bump, точечные правки в 1–2 строки. `code-reviewer` — по желанию.
Принцип glafira №1: **ВЕРИТЬ `pytest`/`tsc`/`build`/`grep`, НЕ верить отчётам агента.** После
каждого агента — независимая проверка (прогон тестов/сборки, чтение диффа, греп на фейки).

⚠️ **Грабли среды (важно):**
1. **npm-реестр здесь дико медленный (~9 c/пакет) — `npm install` ВИСНЕТ.** Не ставить с нуля.
   Зависимости — точное подмножество glafira (те же версии), поэтому `node_modules` копируется
   локально: `rsync -a ../glafira/frontend/node_modules/ ./node_modules/` (≈4 c). Это уже сделано.
2. **Агенты `fastapi-expert`/`react-expert` запинены на мёртвую модель** `claude-sonnet-4-20250514`.
   При запуске через Agent/Workflow ОБЯЗАТЕЛЬНО передавать `model` override (напр. `opus`/`sonnet`),
   иначе агент падает с "model may not exist".

## 1. Стек
- **Backend:** Python 3.12, FastAPI (async) + SQLAlchemy 2 (async, asyncpg + **greenlet**) + Alembic,
  PostgreSQL 16, Pydantic v2 + pydantic-settings. **Redis 7 + arq** — очередь и общий прогресс
  фоновой синхронизации МНО с ФГИС (отдельный сервис `worker`, переживает рестарт/`--workers 2`).
  Auth — JWT (Bearer access + HttpOnly refresh-cookie,
  python-jose) + bcrypt (passlib, **bcrypt<4** + `__about__` shim). Экспорт `.xlsx` — openpyxl
  (серверный). Тесты — pytest + pytest-asyncio.
- **Frontend:** React 18.3 + TypeScript 5.7 (strict, `verbatimModuleSyntax`) + Vite 5,
  react-router-dom 6, @tanstack/react-query 5, zustand 4, axios, lucide-react. **Голый CSS на
  токенах, без Tailwind.** Тулинг и `tokens.css`/`global.css` — из glafira.
- Русский UI, русские комментарии. JetBrains Mono — счётчики/время/координаты. Десктоп-only.

## 2. Single-tenant
Один арендатор. **НЕТ `company_id` нигде, НЕТ биллинг-гейта** (в отличие от glafira). Остаётся JWT
+ DB-локаут входа (5 попыток → 15 мин, anti-enumeration). Роли: `admin` (всё, вкл. управление
пользователями) | `user` (просмотр инцидентов, смена статуса, экспорт; БЕЗ управления пользователями).

## 3. Раскладка (монорепо)
```
backend/   FastAPI: app/{core,config,database,deps,api/v1,models,schemas,services,seed}, alembic/, tests/
frontend/  React+Vite SPA: src/{api/{client,aliases,hooks,mutations},store,lib,components,pages,styles}
contracts/ openapi.json (генерируется из живого бэка позже) + .gitkeep
docs/      BUILD-SPEC.md (контракт скаффолда)
project/   исходный хэндофф Claude Design: прототип react-app/ + ТЗ + дизайн-система _ds/ (НЕ прод-код)
docker-compose.yml / docker-compose.prod.yml / .env.example / .gitignore
```
Сервисы/порты/БД: db `postgres:16` (БД `dedecolog`, volume `dedecolog_pgdata`); backend uvicorn
`app.main:app` :8000 (`DATABASE_URL=postgresql+asyncpg://USER:PASS@db:5432/dedecolog`); frontend
nginx :80 → host :8080, build-arg `VITE_API_BASE_URL`.

## 4. Модель данных (UUID PK `gen_random_uuid()`, `TIMESTAMP(timezone=True)` = UTC)
- **users:** id, email (unique), password_hash, fio, role `admin|user`, **is_superadmin** (bool —
  защищённый главный админ `pulse@reo.ru`: нельзя удалить/разжаловать/сбросить ему пароль чужими
  руками), status `active|invited` (новых юзеров создаём сразу `active` — инвайт/temp_password убран),
  is_active, failed_login_attempts, locked_until, created_at/updated_at.
- **incidents:** id, source `max|form`, status `new|found|none|exported` (деф. `new`), fio, region,
  city, street, coords (текст «lat, lon»), **comment** (прочая НЕ-адресная инфа: «Радар №…» / ФИО из
  текста / описание проблемы — AI кладёт сюда, чтобы не терять), photo_time (фотофиксация, ключ
  сортировки/периода), photos (1..3), photo_urls (JSONB list), msg (id сообщения Макса, nullable),
  **msg_url** (готовый веб-URL сообщения Макс для ссылки), **notified_at** (момент отправки в
  Макс-группу), **quote** (сохранённая цитата), bins (Форма «баки», nullable, скрыто в таблице по
  ТЗ §11), received_at («поступило»), created_at/updated_at.
- **audit_log:** id, action, entity_type, entity_id, changes (JSONB before/after), actor_type
  `human|system`, actor_user_id (FK users SET NULL), created_at. Пишется на каждое изменение статуса/
  массовое изменение/создание/удаление пользователя/смену профиля/сохранение-тест-отключение SMTP.
- **reports:** история сформированных Excel-выгрузок обращений. id, kind (`incidents`), filename
  (человекочит. имя скачивания), row_count, size_bytes, created_by_id (FK users SET NULL),
  created_by_fio (снимок ФИО), created_at. Файл — на диске `{STORAGE_DIR}/reports/{id}.xlsx` (колонки
  пути нет). Генерация СИНХРОННАЯ (в запросе, без arq): reuse `export.build_xlsx` +
  `incident.list_for_export`/`list_by_ids`. ⚠️ фильтры incident_type/mno_id в отчёт НЕ входят (паритет
  со старым GET /incidents/export).
- **smtp_settings:** ЕДИНСТВЕННАЯ строка (single-tenant, get-or-create) — почтовый сервер, настраиваемый
  из UI («Настройки → Почта (SMTP)»). host, port, encryption `tls|ssl|none`, username, **password_enc**
  (Fernet-шифр — НАРУЖУ НИКОГДА не отдаётся), from_email, from_name, status `disconnected|connected`
  (connected только после успешного теста), last_test_at/last_test_ok/last_test_error, created/updated.
  Шифрование — `app/core/crypto.py` (Fernet; ключ из `FERNET_KEY` или дериват из `JWT_SECRET`). ⚠️ Это
  ОТДЕЛЬНЫЙ канал от env-mailer писем волонтёрам (SMTP_* env → verify/reset); каналы независимы.
- Миграции: `0001_initial` (сначала `CREATE EXTENSION pgcrypto`) · `0002` notified_at+quote ·
  `0003` msg_url · `0004` is_superadmin (бэкфилл = старейший admin = pulse@reo.ru) · `0005` comment ·
  `0006` regions+mno · `0007` индекс `ix_mno_fgis_id` (upsert МНО по fgis_id) · `0008` mno.address→TEXT · `0009` lat/lon+индекс · `0010` incidents.incident_type · `0011` incident_types · `0012` volunteers · `0013` volunteers.last_seen_at · `0014` incidents.mno_reg · `0015` volunteers.email_code · `0016` incidents.mno_id · `0017` mno.source (МНО от волонтёра) · `0018` mno.comment+photo_urls · `0019` incidents/mno.volunteer_id (авторство) · `0020` smtp_settings · `0021` reports · `0022` quotes (+ сид пула ~301 из services/quotes_data.py).

## 5. API (`/api/v1`, конверт ошибок `{error:{code,message,details}}`)
- **auth:** `POST /auth/login` → `{access_token,token_type}` + HttpOnly refresh-cookie (path
  `/api/v1/auth/refresh`); `POST /auth/refresh`; `POST /auth/logout`; `GET /auth/me` → UserMe.
- **incidents:** `GET /incidents` (фильтры search/source[]/status[]/**region**/date_from/date_to + sort
  `date|time|region|city|address|status|source` + order + page/page_size → `Paginated[IncidentListItem]`).
  **Поиск (search)** — многословный: токенизируется по пробелам/пунктуации, каждый токен ilike-OR по
  полям, итог AND (порядок слов и запятые не важны; то же в `mno._search_clause`);
  `GET /incidents/funnel` (честят search/source/**region**/period БЕЗ status); `GET /incidents/regions`
  (DISTINCT регионы → дропдаун фильтра); `GET /incidents/export` (.xlsx по фильтру, **полные** URL фото) +
  `POST /incidents/export {ids}`; `POST /incidents/bulk-status {ids,status}`; `POST /incidents/bulk-delete
  {ids}`; `GET /incidents/{id}` → IncidentDetail; `PATCH /incidents/{id}/status {status}`. Статичные роуты
  (funnel/regions/export/bulk-*) объявлены ДО `/{id}`.
- **intake** (приём; заголовок `X-Intake-Token`): `POST /intake/max` (Макс-бот: фото+текст), `POST
  /intake/form` (публичная форма `/form`), `GET /intake/suggest/address` (DaData-Подсказки, прокси),
  `GET /intake/photo/{id}/{file}` (ПУБЛИЧНАЯ отдача фото), `GET /intake/pending-notify` + `POST
  /intake/mark-notified` (для уведомлений maxbot в группу). Свободный текст бота разбирает AI
  (`ai_parse_incident`, claude `-p`, model `CLAUDE_PARSE_MODEL=sonnet`) → region/city/street/coords/time/
  **comment** (Радар/ФИО/описание — в comment, НЕ в адрес); координаты — БЕСПЛАТНЫМИ Подсказками
  (`geocode_address`), платный DaData Clean — фолбэк (в проде 403). Лог — `storage/logs/parse.log`;
  переразбор старых — `python -m app.reprocess [--apply] [--all]`.
- **users** (только admin): `GET /users` (отдаёт is_superadmin); `POST /users {fio,email,role,password}`
  → юзер сразу `active` (инвайт/temp_password УБРАН — пароль задаёт админ, 6..128); `POST
  /users/{id}/password {new_password}` — сброс пароля (ЗАПРЕЩЁН для супер-админа); `DELETE /users/{id}`
  (нельзя удалить супер-админа, admin-роль и себя).
- **profile** (self): `PATCH /profile {fio}` (admin only); `POST /profile/password {new_password}` (без ввода
  текущего, по ТЗ §9.1; min 6 / max 128). ⚠️ password-эндпоинт через `get_current_actor` принимает ОБА
  токена: admin (User) → users, volunteer-токен → volunteers (`volunteer.change_own_password` — смена пароля
  из мобильного приложения, тот же эндпоинт).
- **reports** (любой авторизованный — admin И user, как экспорт): `POST /reports/incidents`
  `{ids?,search?,source?[],status?[],region?,date_from?,date_to?,sort,order}` (ids непуст → по выбранным,
  иначе по фильтру) → 201 ReportListItem (СИНХРОННО формирует .xlsx, пишет файл + строку); `GET /reports`
  (page/page_size) → `Paginated[ReportListItem]` (новейшие первыми); `GET /reports/{id}/download` → .xlsx
  с диска (нет строки/файла → 404); `DELETE /reports/{id}` → `{message}` (удаляет строку+файл).
  ReportListItem = id/kind/filename/row_count/size_bytes/created_by_fio/created_at. ⚠️ `ids` в запросе —
  UUID (не str, иначе `list_by_ids` матчит впустую → 0 строк). **Формирование отчёта СРАЗУ переводит все
  включённые обращения в статус `exported`** (файл собирается ДО перевода — в нём снимок прежних статусов).
- **settings/smtp** (только admin, гейт на роутере): `GET /settings/smtp` → статус (БЕЗ пароля:
  configured/verified/host/port/encryption/username/from_email/from_name/last_test_*); `POST
  /settings/smtp/config {host,port,encryption,username,password,from_email,from_name}` (пароль write-only:
  пусто = не менять; любое сохранение сбрасывает verified) → статус; `POST /settings/smtp/test {to}` →
  `{sent_to,last_test_at}` (реальная отправка smtplib; сервис коммитит исход теста САМ — и успех, и
  ошибку в last_test_error); `POST /settings/smtp/disconnect` → `{message}`. Ядро отправки —
  `services/smtp.send_email` (переиспользуемо под будущие оповещения).
- **.xlsx-выгрузка** — 17 колонок: Заявитель · Источник · Статус · Регион · Город/н.п. · Адрес(улица) ·
  Полный адрес · Координаты · **Комментарий** · Дата фотофиксации(ДД.ММ.ГГГГ) · Время(ЧЧ:ММ) · Кол-во
  фото · **Фото 1 · Фото 2 · Фото 3** · Ссылка на сообщение(Макс) · Поступило. Столбцы «Фото 1/2/3» —
  в ячейку ВСТРАИВАЕТСЯ миниатюра (`{i}_thumb.jpg` с диска через `openpyxl.drawing.image.Image`) — видна
  в ЛЮБОМ Excel/МойОфис/Р7, без интернета и макросов; ячейка несёт гиперссылку на полное фото (клик →
  скачать, нужен интернет). Нет файла → текст-ссылка «Открыть фото». Строки с фото выше, столбцы Фото шире.

## 6. Экраны (фронт)
- **/login** — форма входа (useLogin → /auth/login + /auth/me, redirect /incidents).
- **/incidents** — главный. Шапка (заголовок + счётчик «N обращений…» / «Показано X из N»,
  «Выгрузить всё»), поиск, **воронка** (одиночный выбор статуса, счётчики из /funnel), **фильтры**
  (источник мульти-чипы + **регион**-дропдаун + период «с—по»), **bulk-бар** (выгрузить выбранные / пометить «Выгружен» /
  снять), **таблица** (Фото·Дата·Время·Регион·Город·Адрес·Координаты·**Тип инцидента**·**МНО**(ссылка на
  карточку `/mno?open=id`, реестровый №)·Статус·Источник; тип-подпись резолвится из справочника incident_types),
  сортировка по клику на заголовок (**первый клик — убывание**, повтор — возрастание, ▲/▼), чекбоксы,
  пустое состояние 💚. Строка → **drawer** (карточка вкл. «Комментарий» + смена статуса). Миниатюра → **lightbox**.
- **/reports** — «Отчёты»: история сформированных .xlsx-выгрузок обращений (таблица: дата+время
  формирования · тип · строк · размер · сформировал · скачать/удалить), серверная пагинация `?rpage`,
  пустое состояние 💚. Формируются со страницы «Инциденты»: кнопки «Выгрузить всё»/«Выгрузить в Excel»
  ЗАМЕНЕНЫ на «Сформировать отчёт» (шапка — по фильтру, bulk — по выбранным); прямого скачивания со
  страницы больше нет — файл уходит в «Отчёты». Пункт сайдбара «Отчёты» (icon download), виден всем ролям.
- **/settings** — профиль (Заявитель / email readonly / смена пароля) + блок «Пользователи» (только admin:
  список, бейджи роли/статуса + «Супер-админ», создание юзера С ПАРОЛЕМ (сразу active, без temp_password),
  кнопка «Задать пароль» у каждого, удаление; у супер-админа удаление/сброс скрыты) + блок **«Почта (SMTP)»**
  (только admin: host/порт/шифрование-чипы/логин/пароль(write-only)/from — бейдж статуса «Не настроено /
  Настроено, не проверено / Проверено», честный last_test_error; при configured — тестовое письмо + «Отключить»).
- Фильтры/сортировка живут в URL (`useSearchParams`); строки `React.memo`; CSS скоупится под
  `.de-inc-*` / `.de-set-*`; цвета только через `--ark-*` токены; бренд — эко-зелёный `--de-brand`.

## 7. Команды
**Backend** (локально есть `.venv` python3.14 для проверок; прод — Docker python:3.12):
```bash
cd backend
.venv/bin/python -m pytest -q          # тесты (оффлайн, без внешней БД) — сейчас 382/382 зелёные
.venv/bin/python -m compileall -q app  # синтаксис
# в Docker/проде: alembic upgrade head ; python -m app.seed
```
**Frontend** (⚠️ НЕ запускать `npm install` — реестр виснет; `node_modules` уже скопирован):
```bash
cd frontend
npx tsc --noEmit       # типы — чисто
npm run build          # сборка (tsc -b && vite build) — собирается
npm run dev            # дев-сервер :5173 (нужен бэк на VITE_API_BASE_URL)
```

## 8. Деплой
Пошаговая инструкция для сервера — **`DEPLOY.md`**.
- **Prod по IP (сейчас, без домена):** `docker-compose.prod.yml` — наружу открыт ТОЛЬКО фронт на
  **`<SERVER_IP>:8888`**; nginx фронта проксирует `/api/` → `backend:8000` (тот же origin, без CORS,
  `VITE_API_BASE_URL=/api/v1`); backend и postgres наружу не публикуются. По HTTP/IP обязательно
  `SESSION_COOKIE_SECURE=False`. Завтра домен+HTTPS → Caddy/nginx на 80/443 + `SECURE=True`.
- **CI/CD (как у glafira):** `.github/workflows/deploy.yml` — push в `main` → SSH на VPS → `git pull
  --ff-only` → пересборка изменившейся части → `up -d` → `alembic upgrade head` если менялись миграции.
  При смене `backend/` деплой ДОП. форсит `up -d --force-recreate --no-deps worker frontend` — иначе
  `worker` (образ backend без своего `build:`) крутит СТАРЫЙ код, а nginx фронта кэширует старый IP
  backend → 502. Диагностика синка/зависаний — DEPLOY.md §10.
  Секреты репозитория: `SSH_HOST`/`SSH_USER`/`SSH_PRIVATE_KEY`. Первый деплой (clone + .env + seed) —
  вручную. ⚠️ `.github/workflows/*` пушится только токеном со scope `workflow`.
- **Dev:** `cp .env.example .env && docker compose up --build` (фронт :8080, бек :8000, postgres :5432).
- **Прод сейчас (актуальное):** ЖИВ на **`ecopulse.reo.ru`** (HTTPS, Caddy → :8888). claude CLI — токен
  через `CLAUDE_CODE_OAUTH_TOKEN` в серверном `.env` (**`CLAUDE_TOKEN_FILE` ПУСТОЙ** — файловая шара из
  ArkadyJarvis протухала 401); нужен и для цитат, и для AI-разбора (sonnet). DaData: Подсказки
  (бесплатно) работают, Clean (платный) → 403, не подключён (геокод через Подсказки). maxbot — профиль
  `--profile maxbot`, уведомляет в Макс-группу (`MAX_GROUP_CHAT_ID`). Бэкап БД — `scripts/backup-db.sh` /
  `scripts/restore-db.sh` (см. DEPLOY.md §9).
- **Замечание о среде разработки:** локального Docker/Postgres в ЭТОЙ машине нет — здесь только
  `pytest`/`tsc`/`build`/`grep`; сквозной прогон идёт на сервере (уже работает вживую).

## 9. Правило №1: НЕТ фейковых заглушек
Контрол либо работает по-настоящему, либо честно отключён/подписан. Запрещено: `console.log`/
`alert()`/`print()`-логирование, кнопки-пустышки, молча выкинутые поля схемы, выдуманные CSS-токены,
тесты против несуществующих эндпоинтов. Пример честности: инвайт возвращает реальный временный
пароль и подписан «письмо НЕ отправлено» — не утверждать, что письмо ушло.

## 10. Что сделано сверх скаффолда / что отложено
**СДЕЛАНО и в проде:** публичная форма `/form` (DaData-автокомплит + клиентское сжатие фото + серверный
ресайз), **Макс-бот** (`maxbot/`, long-polling, фото+адрес → инцидент, цитата, уведомления в группу;
в группе бот молчит на не-фото — принимает только фото+подпись), **AI-разбор адреса** (claude `-p`
sonnet) + бесплатный геокод через Подсказки, супер-админ + ручные пароли (инвайт убран), фильтр
региона, поле «Комментарий», ссылки на фото в .xlsx, мотивирующие эко-цитаты (СЛУЧАЙНАЯ из таблицы
`quotes` — пул ~301 в `services/quotes_data.py`, сид миграцией 0022; медленный claude CLI для цитат
УБРАН, `nature_quote()` читает `ORDER BY random()`, фолбэк на код-список),
бэкап-скрипты, домен+HTTPS, **раздел «Интеграция ФГИС УТКО»** (только супер-админ, `/integration`):
живой краулер карты `public-api.utko.mnr.gov.ru` (слой 5) — синхронизация справочника субъектов РФ
(`filters/regions`) и МНО (фильтр→плитка с дроблением кластеров→батч-детали `sidebar/cluster` +
фолбэк на документированный `sidebar/object`: название/адрес/координаты; upsert по `fgis_id`,
потоковая запись). Краул останавливается по ИТОГУ региона (сумма `iconContent` на старт-зуме = счётчик ФГИС → не домалывает собранное вхолостую; старое «плато» убрано — недобирало города; MAX_Z=16, лимит тайлов 100000). На батч деталей — таймаут `DETAIL_TIMEOUT=120с` + `rollback` при сбое (не виснет/не рушит транзакцию каскадом); лог каждого батча и хода обхода в воркере (arq глушил логгеры `app.*` → включены в `worker._configure_app_logging`). Синхронизация — через **Redis+arq** (сервис `worker`): веб кладёт задачу в
очередь, воркер краулит, прогресс/статус в Redis (общий для `--workers 2`, переживает рестарт);
прогон «Все регионы» **возобновляется** (done-set пройденных регионов). Округ регионов — по
встроенной карте `region_fed` (ФГИС нумерует id 1..85 подряд; хвост 80–85 ≠ автокоды: 82=Чукотка,
83=ЯНАО, 84=Крым, 85=Севастополь). Обратный геокод НЕ нужен — адрес отдаёт `sidebar`.
**Почтовый сервер в UI («Настройки → Почта (SMTP)», только admin):** редактируемый из интерфейса SMTP
(таблица `smtp_settings`, single-tenant, пароль Fernet-шифром `password_enc` — наружу не отдаётся) +
тестовое письмо (реальная отправка stdlib `smtplib` ssl/tls/none, честный маппинг ошибок → last_test_error,
лог `storage/logs/smtp.log`). Ядро `services/smtp.send_email` — ЕДИНЫЙ канал почты приложения: письма
волонтёру (код подтверждения почты + ссылка сброса пароля, `services/volunteer.py`) идут через него же.
Старый env-mailer (`services/mailer.py`) УДАЛЁН; env-поля `SMTP_*` — legacy, кодом не читаются.
**QA-фиксы (дефект-лист):** #9 — `POST /profile/password` принимает и volunteer-токен (смена пароля из
приложения через тот же эндпоинт); #17 — `GET /mno?sort=distance&lat&lon` — серверная сортировка по
расстоянию (эквидистантная аппроксимация без тригонометрии в SQL, NULL-координаты в конец), пагинация
остаётся серверной; #18 — многословный/безпунктуационный поиск (токенизация + AND) в mno/incidents.
**Отложено/заброшено:** Яндекс-Форма webhook — ЗАБРОШЕН (нужен IPv6, VPS IPv4-only → сделали свою
форму, `/intake/yandex` остался неиспользуемым); реальные письма (invite/reset) — НЕ нужны (пароли
задаём руками); DaData Clean (платный) — не подключаем (геокод бесплатными Подсказками).

## 11. Известные мелкие хвосты (low, отложены осознанно)
- `auth.py`: при истёкшем локауте сброс счётчика не персистится, если затем юзер оказался inactive
  (косметика; реордер логики отложен, чтобы не рисковать lockout-семантикой).
- Несколько scaffold-примитивов (`useMe`, `RoleGuard`, `ui/EmptyState`, `store/uiStore`) объявлены,
  но пока не подключены — заготовки под рост приложения (не фейк-контролы, сборку не ломают).
- `contracts/openapi.json` ещё не сгенерён (нет живого бэка) — фронт-типы в `src/api/aliases.ts`
  написаны руками строго по §5; после первого живого запуска: регенерить + `npm run types:gen`.

## 12. Версия
`frontend/src/lib/version.ts` (`APP_VERSION`). Бампить на каждый значимый деплой; формат коммита —
`vX.Y.Z тип(scope): описание` (версия первым токеном, как в glafira).
