# BUILD SPEC — ЭкоПульс (v1 scaffold)

> Admin panel for an ecologist/inspector to triage TKO-site reports. Built on the **glafira stack & conventions** (FastAPI async + React 18 / TS / Vite). This file is the **single source of truth** for the scaffold. Faithful behavior contract = `project/react-app/` source + `project/docs/ТЗ - ЭкоПульс.md`.

## 0. Reference material (READ THESE)
- **Behavior/ТЗ:** `project/docs/ТЗ - ЭкоПульс.md`
- **Prototype source (functional contract):** `project/react-app/{App.jsx,data.js,styles.css,components/*.jsx}`
- **Recon blueprints (deep patterns extracted from glafira — READ the relevant one before building your half):**
  - Backend infra: `/private/tmp/claude-501/-Users-artemsitnikov-claudeproject-dedecology/d2243561-7cd1-44f8-b7f5-9119e51561e7/scratchpad/recon/backend-infra.md`
  - Backend module pattern: `…/scratchpad/recon/backend-module-pattern.md`
  - Frontend infra: `…/scratchpad/recon/frontend-infra.md`
  - Frontend tokens: `…/scratchpad/recon/frontend-tokens.md`
  - Frontend screen pattern: `…/scratchpad/recon/frontend-screen-pattern.md`
  - Prototype behavior: `…/scratchpad/recon/prototype-behavior.md`
- **Live glafira reference code:** `/Users/artemsitnikov/claudeproject/glafira/backend` and `/Users/artemsitnikov/claudeproject/glafira/frontend` — copy/adapt patterns from here.

## 1. Locked decisions
- **Single-tenant.** NO `company_id` anywhere, NO billing gate. Keep JWT (Bearer access + HttpOnly refresh cookie) + DB-backed login lockout.
- **Backend `.xlsx` export** via openpyxl (server-side, exports full filtered/selected set).
- **Operator admin first.** Build auth + incidents + settings/users + export, seeded with the 13 demo incidents. The Макс/Яндекс-Форма webhooks, address geocoder, and real invite/reset **emails are a LATER pass** — the data model must be ready for them but do NOT implement ingestion or email now.
- **Roles:** `admin` (full) | `user` (view incidents, change status, export; NO user management).
- **UUID** primary keys (`gen_random_uuid()` — initial migration must `CREATE EXTENSION IF NOT EXISTS pgcrypto`).
- **No fake stubs** (glafira's #1 rule): a control either works for real or is honestly disabled/labeled. No `console.log`, no `alert()`, no `print()` for logging, no buttons that do nothing, no schema fields silently dropped. Invite returns a real temp password (no email yet) — do NOT claim an email was sent.
- **Monorepo root** = `/Users/artemsitnikov/claudeproject/dedecology/` (siblings of existing `project/`): create `backend/`, `frontend/`, `contracts/`, `docs/` + root `docker-compose*.yml`, `.env.example`, `.gitignore`, `CLAUDE.md`.

## 2. Data model (single-tenant, UUID PKs, `TIMESTAMP(timezone=True)`)

### User → table `users`
| col | type | notes |
|---|---|---|
| id | UUID PK | `server_default gen_random_uuid()` |
| email | String(255) unique not null | global unique |
| password_hash | String(255) not null | bcrypt; invited users get a generated temp password |
| fio | String(255) not null | |
| role | String(10) not null default `'user'` | CHECK `IN ('admin','user')` + Pydantic `Literal` |
| status | String(10) not null default `'active'` | CHECK `IN ('active','invited')`; flip `invited`→`active` on first successful login |
| is_active | Boolean not null default true | |
| failed_login_attempts | Integer not null default 0 | |
| locked_until | TIMESTAMP(tz) nullable | |
| created_at / updated_at | TimestampMixin | |

### Incident → table `incidents`
| col | type | notes |
|---|---|---|
| id | UUID PK | |
| source | String(8) not null | CHECK `IN ('max','form')` + Literal |
| status | String(12) not null default `'new'` | CHECK `IN ('new','found','none','exported')` + Literal |
| fio | String(255) not null default `''` | заявитель |
| region | String(255) not null default `''` | |
| city | String(255) not null default `''` | |
| street | String(500) not null default `''` | улица/дом (+ «Радар №…» for Макс) |
| coords | String(64) not null default `''` | "lat, lon" text |
| photo_time | TIMESTAMP(tz) nullable | дата/время фотофиксации (sort + period filter key) |
| photos | Integer not null default 1 | count 1..3 |
| photo_urls | JSONB not null default `[]` | list[str] (seed: placeholder image paths/data) |
| msg | String(120) nullable | Макс message id (link `https://max.ru/m/{msg}` built on FE) |
| bins | Boolean nullable | Форма «баки раздельного сбора» (in model, hidden in table per ТЗ §11) |
| received_at | TIMESTAMP(tz) not null | `server_default now()` — «поступило» |
| created_at / updated_at | TimestampMixin | |

### AuditLog → table `audit_log` (glafira pattern, minus company_id)
`id UUID`, `action String(60)`, `entity_type String(60)`, `entity_id UUID nullable`, `changes JSONB nullable ({before,after})`, `actor_type String(10) CHECK IN ('human','system') default 'human'`, `actor_user_id UUID FK users ondelete SET NULL nullable`, `created_at` (CreatedAtMixin). Write an audit row for every mutating action (status change, bulk status, user create/delete, profile/password change).

## 3. API contract — all under `/api/v1`, error envelope `{error:{code,message,details}}`

### `/auth`
- `POST /auth/login` `{email,password}` → `200 {access_token, token_type:"bearer"}` + Set-Cookie `refresh_token` (HttpOnly, SameSite=lax, path `/api/v1/auth/refresh`, max-age 14d, Secure from settings). Lockout: 5 fails → 15-min `locked_until` (429 `ACCOUNT_LOCKED`); unknown email → same 401 `INVALID_CREDENTIALS` (anti-enumeration); inactive → 403 `USER_INACTIVE`. On success: reset counter; if `status=='invited'` set `'active'`.
- `POST /auth/refresh` (reads cookie) → `{access_token, token_type}`.
- `POST /auth/logout` → `{message}` + delete cookie.
- `GET /auth/me` → `UserMe {id, email, fio, role, status}`.

### `/incidents`
- `GET /incidents` query: `search`, `source` (repeatable: `max`/`form`), `status` (repeatable), `date_from` (YYYY-MM-DD), `date_to` (YYYY-MM-DD), `sort` (`date|time|region|city|address|status|source`, default `date`), `order` (`asc|desc`, default `desc`), `page` (≥1), `page_size` (1..200, default 100) → `Paginated[IncidentListItem]` (`{items,total,page,page_size,pages}`).
  - **search:** case-insensitive substring across `fio,region,city,street,coords,msg` (OR within, AND with other filters).
  - **source/status:** `IN (...)` lists.
  - **period:** `photo_time` between `date_from 00:00:00` and `date_to 23:59:59` inclusive (filter on **photo_time**, not received_at).
  - **sort:** `date|time`→`photo_time`; `address`→`street`; `status`→CASE order `new<found<none<exported`; `source`→`source`; others→same-named col. default `photo_time desc`.
- `GET /incidents/funnel` query: `search,source,date_from,date_to` (same as list, **excluding** status) → `FunnelCounts {all,new,found,none,exported}` (counts honor search/source/period but NOT the status filter — so each chip shows its candidate count). **Declare this route BEFORE `/{id}`.**
- `GET /incidents/export` (same query as list) → `.xlsx` of the full filtered set, `Content-Disposition: attachment; filename*=UTF-8''Инциденты_ЭкоПульс.xlsx`. **Declare before `/{id}`.**
- `POST /incidents/export` `{ids:[uuid,…]}` → `.xlsx` of selected, filename `Инциденты_ЭкоПульс_выбранные.xlsx`. **Declare before `/{id}`.**
- `GET /incidents/{id}` → `IncidentDetail` (all fields incl. `bins`).
- `PATCH /incidents/{id}/status` `{status}` → `IncidentDetail` (audit).
- `POST /incidents/bulk-status` `{ids:[…], status}` → `{updated:int}` (audit). Powers «Пометить Выгружен».
- **xlsx columns (order, per ТЗ §7 / prototype `toCsv`):** ФИО · Источник(label) · Статус(label) · Регион · Город / н.п. · Адрес (улица) · Полный адрес(`region, city, street`) · Координаты · Дата фотофиксации(`ДД.ММ.ГГГГ`) · Время фотофиксации(`ЧЧ:ММ`) · Кол-во фото · Ссылка на сообщение(`https://max.ru/m/{msg}` for max else `''`) · Поступило(`received_at`).

### `/users` (gate `require_admin`)
- `GET /users` → `[UserListItem {id,fio,email,role,status}]`.
- `POST /users` `{fio,email,role}` → `201 UserCreateResult {id,fio,email,role,status:'invited',temp_password}`. Creates an **invited** user with a generated temp password (`secrets.token_urlsafe(12)`); returns it once. NO email sent (label honestly on FE). 409 `CONFLICT` on duplicate email.
- `DELETE /users/{id}` → `204`. Reject deleting an `admin`-role user (ТЗ lock → 403 `FORBIDDEN`) and deleting self.

### `/profile` (self)
- `PATCH /profile` `{fio}` → `UserMe`.
- `POST /profile/password` `{new_password}` (min_length 6) → `{message}`. No current-password check (ТЗ §9.1). audit.

## 4. Backend file tree (`backend/`, layered like glafira; adapt glafira files, strip company_id/billing)
```
backend/
  requirements.txt        Dockerfile        pytest.ini        alembic.ini
  alembic/{env.py, script.py.mako, versions/<initial>.py}
  app/
    __init__.py  main.py  config.py  database.py  deps.py  seed.py
    core/{__init__.py, errors.py, security.py, pagination.py, permissions.py}
    models/{__init__.py, base.py, user.py, incident.py, audit.py}
    schemas/{__init__.py, base.py, auth.py, user.py, incident.py}
    services/{__init__.py, auth.py, user.py, incident.py, audit.py, export.py}
    api/{__init__.py, v1/{__init__.py, router.py, auth.py, incidents.py, users.py, profile.py}}
  tests/{conftest.py, test_auth.py, test_incidents.py, test_users.py}
```
- `deps.py::get_current_user` (no company, no billing). `get_current_admin`/`require_admin` in `core/permissions.py`.
- `seed.py` (`python -m app.seed`, idempotent): admin user (`admin@dedekolog.ru` / a default password from settings; role admin, status active) + 2 demo users (1 user/active, 1 user/invited) + the **13 demo incidents** from `project/react-app/data.js` (map fields; `photo_time` parsed from `photoTime` "DD.MM.YYYY, HH:MM"; `received_at` from `dateRaw`; `photo_urls` = N placeholder paths). Reuse glafira `seed.py` structure (exists-guards).
- requirements.txt: copy glafira's TOP block + `openpyxl`; **drop** fastembed/pgvector/telethon/qrcode/reportlab/python-docx/cryptography(Fernet not needed)/jinja2. Keep `bcrypt>=3.2.0,<4.0.0` (critical pin) + the bcrypt `__about__` shim in security.py.
- Dockerfile: `python:3.12-slim`, no Node/fastembed. pytest.ini: `asyncio_mode=auto`, `pythonpath=.`.
- Tests: offline (no live LLM), use httpx + a test DB session; minimal positive+negative per endpoint. `httpx` response `.json()`/`.status_code` are SYNC → MagicMock not AsyncMock (glafira grable).

## 5. Frontend file tree (`frontend/`, copy glafira tooling verbatim)
```
frontend/
  index.html  package.json  vite.config.ts  tsconfig.json  tsconfig.node.json
  nginx.conf  Dockerfile  .env.example  .nvmrc  .dockerignore
  src/
    main.tsx  App.tsx  vite-env.d.ts
    styles/{tokens.css, global.css}        ← COPY from glafira/frontend/src/styles (see §6)
    api/{client.ts, aliases.ts, hooks/{useMe.ts,useIncidents.ts,useFunnelCounts.ts,useUsers.ts}, mutations/{useLogin.ts,incidents.ts,users.ts,profile.ts}}
    store/{authStore.ts, uiStore.ts}
    lib/{version.ts, format.ts, status.ts}
    components/{AppLayout.tsx, Sidebar.tsx, Sidebar.css, RoleGuard.tsx, ui/{Icon.tsx, Avatar.tsx, EmptyState.tsx}}
    pages/
      LoginPage.tsx  LoginPage.css
      incidents/{IncidentsPage.tsx, IncidentsTable.tsx, Funnel.tsx, FilterBar.tsx, DetailDrawer.tsx, Lightbox.tsx, Incidents.css}
      settings/{SettingsPage.tsx, Settings.css}
```
- **Exact deps from glafira** `package.json` (React 18.3.1, TS 5.7.2, Vite 5.4.11, react-router-dom 6.28, @tanstack/react-query 5.62 + devtools, zustand 4.5.5, axios 1.7.7, lucide-react 1.16; drop recharts + react-international-phone). name `dedecolog-frontend`.
- `client.ts`: copy glafira's axios client but **drop the 402/SUBSCRIPTION_EXPIRED block**; keep Bearer request interceptor + deduped 401→`/auth/refresh` retry + `normalizeApiError`.
- `authStore.ts`: memory-only token + refresh-cookie bootstrap (drop `subscriptionExpired`). `uiStore.ts` persist key `'dedecolog-ui'`.
- `App.tsx`: `RequireAuth` (refresh-bootstrap) wrapping `AppLayout`; routes `/login`, `/`→`<Navigate to="/incidents">`, `/incidents`, `/settings`, `*`→404. `RoleGuard roles={['admin'|'user']}` (Settings users-block is admin-only inside the page, not a route gate).
- `aliases.ts`: **hand-write** TS types matching the Pydantic schemas (no live server to run `openapi-typescript` yet). Add the `types:gen` script for later. Single import surface for domain types: `Incident`, `IncidentListItem`, `Paginated<T>`, `FunnelCounts`, `UserMe`, `UserListItem`, `ApiError`, etc.
- **Filters live in the URL** (`useSearchParams`) like glafira's funnel screen; `React.memo` rows; per-screen CSS scoped under a wrapper class (use `.de-inc-*` for incidents, `.de-set-*` for settings).
- `lib/status.ts`: `STATUS`/`SOURCE` meta (label + token colors). Map to tokens: new→`--ark-blue-50/--ark-blue-600/--accent`, found→`--ark-red-100/--ark-red-600/--ark-red-500`, none→`--ark-gray-200/--ark-gray-600/--ark-gray-500`, exported→`--ark-green-100/--ark-green-600/--ark-green-500`; source max→`--ark-violet-100/--ark-violet-500`, form→`--ark-yellow-100/--ark-yellow-600`.

## 6. Design tokens (LOCK the visuals)
- Copy `glafira/frontend/src/styles/tokens.css` and `global.css` **verbatim** into `frontend/src/styles/`, with two edits to `tokens.css`:
  - Re-theme the brand to **eco green** (prototype sidebar mark is green gradient): add `--de-brand: #1F8A5B; --de-brand-light: #3FB36B;` and set `--brand-accent: #1F8A5B; --brand-accent-strong: #128640; --brand-bg:#ECF8F0; --brand-border:#A7DDB9; --brand-fg:#128640;` so the `:focus-visible` ring (which uses `--brand-accent`) is eco-green, not glafira pink. Keep the **blue `--accent: #2A8AF0`** (prototype uses blue for active/links).
  - You may drop glafira's ATS-only domain tokens (`--stage-*`, `--score-*`, `--risk-*`, `--src-*`) — not needed.
- Fonts via `<link>` in `index.html` (Inter 400;500;600;700 + JetBrains Mono 400;500) — same as glafira. `lang="ru"`, title `ЭкоПульс — сбор обращений`.
- The prototype's inline colors all already equal `--ark-*` values, so map every prototype hex to its token (e.g. `#EAF3FE`→`var(--ark-blue-50)`, `#2A8AF0`→`var(--accent)`). Do NOT paste raw hex — use tokens.
- Sidebar brand: green-gradient 34px rounded mark with 💚 emoji, title `ЭкоПульс`, subtitle `сбор обращений`. Nav: `Инциденты` (count badge) + `Настройки`. User card at bottom.

## 7. Behavior contract (port the prototype 1:1 — see prototype-behavior.md)
- **Incidents screen:** header (title «Инциденты» + counter «N обращений · обновлено сегодня» / «Показано X из N» when filtered + «Выгрузить всё» button → backend export of current filter). Search row (300px field, placeholder «Поиск по адресу, ФИО, координатам…», hint «Сортировка — по клику на заголовок столбца»). **Funnel** chips (single-select status; order: Все | Новый→Инцидент обнаружен | Выгружен | Нет инцидента; mono counts from `/incidents/funnel`). **FilterBar** (Источник multi-select chips Макс/Яндекс форма; Период two native date inputs «с — по» with ✕ clear; «Сбросить» when active). **Bulk bar** (when rows selected: «Выбрано N», green «Выгрузить в Excel»→POST export selected, «Пометить Выгружен»→bulk-status, «Снять выделение»). **Table** 10 cols in order: Фото(thumb+count badge, click→lightbox) · Дата · Время(mono) · Регион · Город · Адрес(flex) · Координаты(mono) · Статус(pill+dot) · Источник(pill) · Чат(Макс→link, Форма→empty). Checkbox col + select-all. Header-click sort (first click desc, repeat asc; ▲/▼ indicator, active in accent). Row click→drawer. Empty state (💚 circle, «Ничего не найдено», «Сбросить фильтры»).
- **DetailDrawer:** right slide-over (560px) over `rgba(15,22,32,.4)`. Header: source+status pills, `fullAddr` title, ✕. Photos (click→lightbox). Fields: ФИО, Регион, Город/н.п., Адрес, Координаты, Дата/Время фотофиксации, Фотографий, Источник, Поступило. Для Макса: «Открыть сообщение в Максе» link. Status-change chips (4 statuses; active=current; click→PATCH status, live update + invalidate list+funnel).
- **Lightbox:** full-screen `rgba(15,22,32,.84)`; arrows + mono counter `i/N` when >1 photo; caption=fullAddr; click bg/✕ closes.
- **Settings:** title «Настройки». Profile card: ФИО editable, Email readonly, «Сохранить»→PATCH /profile; «Смена пароля»: new-password field + «Сбросить»→POST /profile/password. Users card (admin-only): list with avatar-initials, ФИО+email, role badge (Администратор violet / Пользователь gray), status badge (Активен green / Приглашён amber); invite form (ФИО + email + access chips Пользователь/Администратор + «Отправить приглашение»→POST /users, then show the returned temp password honestly, e.g. «Пользователь добавлен. Временный пароль: …»); delete trash for non-admins, lock icon for admins. Success notices via a banner.

## 8. Deploy / infra (root, mirror glafira)
- `docker-compose.yml` (dev): `db postgres:16` (env POSTGRES_USER/PASSWORD/DB, volume `dedecolog_pgdata`, healthcheck pg_isready, port 5432), `backend` (build ./backend, env_file .env, `DATABASE_URL=postgresql+asyncpg://USER:PASS@db:5432/dedecolog`, depends_on db healthy, command `sh -c "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"`, port 8000, bind-mount `./backend:/app`), `frontend` (build ./frontend arg VITE_API_BASE_URL=http://localhost:8000/api/v1, port 5173→? use vite preview or nginx; for dev simplest: build static + nginx on 8080). 
- `docker-compose.prod.yml`: same but `--workers 2` no reload, ports bound `127.0.0.1`, restart unless-stopped, db not published.
- `.env.example`: `POSTGRES_USER/PASSWORD/DB`, `DATABASE_URL`, `JWT_SECRET` (gen note), `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=14`, `LOGIN_MAX_ATTEMPTS=5`, `LOGIN_LOCKOUT_MINUTES=15`, `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `CORS_ORIGINS=http://localhost:5173,http://localhost:8080`, `SESSION_COOKIE_SECURE=False`, `VITE_API_BASE_URL`.
- `.gitignore`: node_modules, dist, __pycache__, .env, *.pyc, .venv, storage, .DS_Store, *.tsbuildinfo.
- `CLAUDE.md`: a scaled-down project guide (stack, single-tenant note, layout, deploy, the no-fake-stubs rule, deferred ingestion phase).
- `contracts/`: keep a `.gitkeep` + note that `openapi.json` will be generated from the live backend later (then `npm run types:gen`).

## 9. Gotchas (from recon — DO NOT trip on these)
- bcrypt **must** be `<4` + keep the `__about__` shim, else `verify_password` silently returns False.
- `FastAPI(redirect_slashes=False)` → match trailing slashes exactly.
- Static routes (`/funnel`, `/export`, `/bulk-status`) declared **before** dynamic `/{id}`.
- Services raise `AppError` subclasses, never `HTTPException`. Routers commit after service `flush()` (auth service commits internally).
- `_json_serializer = json.dumps(v, default=str)` on the async engine (JSONB with UUID/datetime).
- `expire_on_commit=False`; build responses via `.model_validate(obj)`.
- alembic `env.py`: escape `%` in DATABASE_URL; `target_metadata = Base.metadata`; async `NullPool`. Initial migration creates `pgcrypto` extension first. One alembic head.
- Frontend `verbatimModuleSyntax: true` → **`import type`** for type-only imports. `noUnusedLocals/Parameters` will fail the build on dead code.
- Access token in memory only; reload bootstraps via `/auth/refresh` cookie + `withCredentials: true` → backend CORS `allow_credentials=True` + explicit origins (not `*`).
- Russian UI copy + Russian code comments throughout. JetBrains Mono for counts/time/coords.
</invoke>
