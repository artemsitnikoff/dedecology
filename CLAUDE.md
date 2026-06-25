# CLAUDE.md — ДедЭколог

> Читается первым. Админ-панель эколога/инспектора для триажа обращений о состоянии площадок ТКО.
> Построена на стеке и конвенциях соседнего проекта **glafira**. Единый источник правды для
> скаффолда — `docs/BUILD-SPEC.md`; контракт **поведения/вёрстки** — прототип `project/react-app/`
> + ТЗ `project/docs/ТЗ - ДедЭколог.md`. Скриншоты в `project/screenshots/` — устаревшая
> card-итерация, НЕ ориентир (контракт = исходники прототипа + ТЗ).

---

## 0. Как здесь работают
Реализацию ведут субагенты `fastapi-expert` (бэк) и `react-expert` (фронт) + `code-reviewer`.
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
  PostgreSQL 16, Pydantic v2 + pydantic-settings. Auth — JWT (Bearer access + HttpOnly refresh-cookie,
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
- **users:** id, email (unique), password_hash, fio, role `admin|user`, status `active|invited`
  (флипается `invited→active` при первом успешном входе), is_active, failed_login_attempts,
  locked_until, created_at/updated_at.
- **incidents:** id, source `max|form`, status `new|found|none|exported` (деф. `new`), fio, region,
  city, street, coords (текст «lat, lon»), photo_time (фотофиксация, ключ сортировки/периода),
  photos (1..3), photo_urls (JSONB list), msg (id сообщения Макса, nullable), bins (Форма «баки»,
  nullable, скрыто в таблице по ТЗ §11), received_at («поступило»), created_at/updated_at.
- **audit_log:** id, action, entity_type, entity_id, changes (JSONB before/after), actor_type
  `human|system`, actor_user_id (FK users SET NULL), created_at. Пишется на каждое изменение статуса/
  массовое изменение/создание/удаление пользователя/смену профиля.
- Миграция одна: `alembic/versions/0001_initial.py` (сначала `CREATE EXTENSION pgcrypto`).

## 5. API (`/api/v1`, конверт ошибок `{error:{code,message,details}}`)
- **auth:** `POST /auth/login` → `{access_token,token_type}` + HttpOnly refresh-cookie (path
  `/api/v1/auth/refresh`); `POST /auth/refresh`; `POST /auth/logout`; `GET /auth/me` → UserMe.
- **incidents:** `GET /incidents` (фильтры search/source[]/status[]/date_from/date_to + sort
  `date|time|region|city|address|status|source` + order + page/page_size → `Paginated[IncidentListItem]`);
  `GET /incidents/funnel` (счётчики `{all,new,found,none,exported}`, честят search/source/period БЕЗ
  status); `GET /incidents/export` (.xlsx по фильтру) + `POST /incidents/export {ids}` (.xlsx выбранных);
  `POST /incidents/bulk-status {ids,status}`; `GET /incidents/{id}` → IncidentDetail;
  `PATCH /incidents/{id}/status {status}`. Статичные роуты объявлены ДО `/{id}`.
- **users** (только admin): `GET /users`; `POST /users {fio,email,role}` → `{...,status:'invited',
  temp_password}` (письмо НЕ шлётся — честно показываем временный пароль); `DELETE /users/{id}`
  (нельзя удалить admin-роль и себя).
- **profile** (self): `PATCH /profile {fio}`; `POST /profile/password {new_password}` (без ввода
  текущего, по ТЗ §9.1; min 6 / max 128).
- **.xlsx-выгрузка** — 13 колонок в порядке ТЗ §7: ФИО · Источник · Статус · Регион · Город/н.п. ·
  Адрес(улица) · Полный адрес · Координаты · Дата фотофиксации(ДД.ММ.ГГГГ) · Время(ЧЧ:ММ) ·
  Кол-во фото · Ссылка на сообщение(Макс) · Поступило.

## 6. Экраны (фронт)
- **/login** — форма входа (useLogin → /auth/login + /auth/me, redirect /incidents).
- **/incidents** — главный. Шапка (заголовок + счётчик «N обращений…» / «Показано X из N»,
  «Выгрузить всё»), поиск, **воронка** (одиночный выбор статуса, счётчики из /funnel), **фильтры**
  (источник мульти-чипы + период «с—по»), **bulk-бар** (выгрузить выбранные / пометить «Выгружен» /
  снять), **таблица** 10 колонок (Фото·Дата·Время·Регион·Город·Адрес·Координаты·Статус·Источник·Чат),
  сортировка по клику на заголовок (**первый клик — убывание**, повтор — возрастание, ▲/▼), чекбоксы,
  пустое состояние 👴. Строка → **drawer** (карточка + смена статуса). Миниатюра → **lightbox**.
- **/settings** — профиль (ФИО / email readonly / смена пароля) + блок «Пользователи» (только admin:
  список, бейджи роли/статуса, инвайт с честным temp_password, удаление/замок для admin).
- Фильтры/сортировка живут в URL (`useSearchParams`); строки `React.memo`; CSS скоупится под
  `.de-inc-*` / `.de-set-*`; цвета только через `--ark-*` токены; бренд — эко-зелёный `--de-brand`.

## 7. Команды
**Backend** (локально есть `.venv` python3.14 для проверок; прод — Docker python:3.12):
```bash
cd backend
.venv/bin/python -m pytest -q          # тесты (оффлайн, без внешней БД) — сейчас 23/23 зелёные
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
  Секреты репозитория: `SSH_HOST`/`SSH_USER`/`SSH_PRIVATE_KEY`. Первый деплой (clone + .env + seed) —
  вручную. ⚠️ `.github/workflows/*` пушится только токеном со scope `workflow`.
- **Dev:** `cp .env.example .env && docker compose up --build` (фронт :8080, бек :8000, postgres :5432).
- **Замечание о среде разработки:** локального Docker/Postgres в этой машине нет — сквозной смоук-тест
  (логин→таблица→статусы→.xlsx) ещё НЕ прогонялся вживую; «компилируется/тесты/сборка зелёные» ≠
  «прогнан end-to-end». Первый запуск — на сервере по `DEPLOY.md`.

## 9. Правило №1: НЕТ фейковых заглушек
Контрол либо работает по-настоящему, либо честно отключён/подписан. Запрещено: `console.log`/
`alert()`/`print()`-логирование, кнопки-пустышки, молча выкинутые поля схемы, выдуманные CSS-токены,
тесты против несуществующих эндпоинтов. Пример честности: инвайт возвращает реальный временный
пароль и подписан «письмо НЕ отправлено» — не утверждать, что письмо ушло.

## 10. Отложенная фаза (НЕ реализуется сейчас — выбор «оператор-админка сначала»)
Приём из Макса и Яндекс-Формы (webhooks), геокодер адресов, реальные письма (invite/reset). Модель
данных под них готова (`source`, `msg`, `coords`, `bins`, `status='invited'`), ингестию/почту строим
отдельным поздним этапом.

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
</content>
