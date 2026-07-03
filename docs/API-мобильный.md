# API «ЭкоПульс» — документация для мобильного приложения

> Триаж обращений о состоянии площадок ТКО. Документ описывает REST-эндпоинты,
> сгруппированные по **разделам** (совпадают с тегами Swagger `/docs`).
> Единый машиночитаемый контракт — [`contracts/openapi.json`](../contracts/openapi.json)
> (генерируется из живого приложения).

## Общее

- **Base URL:** `/api/v1` (например, `https://ecopulse.reo.ru/api/v1`).
- **Формат:** JSON (`Content-Type: application/json`), кроме приёма фотоотчёта
  (`multipart/form-data`) и отдачи фото (`image/jpeg`).
- **Кодировка:** UTF-8. Все временные метки — UTC, ISO 8601
  (`2026-06-25T14:30:00+00:00`).
- **Идентификаторы:** сущности (обращения, МНО, пользователи) адресуются по `UUID`.
  Регион адресуется по **коду субъекта РФ** (строка, например `"63"`).

### Авторизация

| Тип доступа | Механизм |
|---|---|
| Защищённые эндпоинты (реестр, МНО, регионы, профиль) | `Authorization: Bearer <access_token>` — access-токен из `POST /auth/login` |
| Приём server-to-server (вебхуки Яндекс-Формы / Макс-бота, очередь уведомлений) | заголовок `X-Intake-Token: <секрет>` |
| Публичная форма волонтёра `POST /intake/form` | без авторизации; анти-спам — honeypot-поле `website` |
| Отдача фото `GET /intake/photo/...` | публично, без авторизации |
| Подсказки адреса `GET /intake/suggest/address` | публично, без авторизации |

Access-токен живёт `ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию 30 мин).
Долгоживущий **refresh-токен** сервер кладёт в `HttpOnly`-cookie `refresh_token`
(path `/api/v1/auth/refresh`); обновление access-токена — через `POST /auth/refresh`.

### Конверт ошибок

Любая ошибка возвращается единым конвертом (см. раздел [Ошибки](#раздел-ошибки)):

```json
{ "error": { "code": "NOT_FOUND", "message": "Инцидент не найден", "details": null } }
```

---

## Оглавление

0. [Волонтёры — регистрация и вход (мобильное приложение)](#раздел-волонтёры)
1. [Авторизация](#раздел-авторизация)
2. [Профиль пользователя](#раздел-профиль-пользователя)
3. [Регионы](#раздел-регионы)
4. [Карта и МНО](#раздел-карта-и-мно)
5. [Карточка МНО](#раздел-карточка-мно)
6. [Отправка фотоотчёта](#раздел-отправка-фотоотчёта)
7. [Добавление нового МНО](#раздел-добавление-нового-мно)
8. [Загрузка фото](#раздел-загрузка-фото)
9. [Админский реестр](#раздел-админский-реестр)
10. [Ошибки](#раздел-ошибки)

> Разделы **«Экспорт (.xlsx)»**, **«Приём вебхуков (server-to-server)»** и
> **«Управление пользователями»** в мобильный API не входят и здесь не документируются
> (эндпоинты присутствуют в Swagger под соответствующими тегами).

---

<a id="раздел-волонтёры"></a>
## 0. Волонтёры — регистрация и вход (мобильное приложение)

Волонтёр — пользователь **мобильного приложения**, отдельная сущность от админки (своя таблица,
свой JWT с claim `typ=volunteer`). Эндпоинты `/volunteer/*`. Раздел «1. Авторизация» ниже — для
эколога/инспектора (веб-админка), волонтёры им не пользуются.

> **Письма (важно):** SMTP пока не подключён, поэтому `register`/`register/resend` возвращают
> **4-значный код прямо в ответе** (`email_sent: false` + `email_verify_code`), а `password/reset-request`
> — reset-токен (`reset_token`) — для интеграции и тестов. Когда подключат SMTP, письмо уйдёт на почту, а
> код/токен в ответе исчезнет (`email_sent: true`). Приложение должно работать в обоих режимах:
> `email_sent=false` → взять код/токен из ответа; `true` → ждать письма.

### POST /volunteer/register
Регистрация волонтёра. **Публичный.** Подтверждение почты — **4-значным кодом** (OTP).
- **Тело:** `{ "email": "v@mail.ru", "password": "≥6 симв.", "repeat_password": "то же" }`
- **200:** `{ "volunteer_id", "email", "email_sent": false, "code_length": 4, "resend_after": 60, "email_verify_code": "3116" }`
  — `email_verify_code` только при `email_sent=false`; `code_length` = сколько ячеек рисовать; `resend_after` = сек до повторной отправки.
- Пароли не совпали → `400 PASSWORDS_MISMATCH`; дубль email → `409 CONFLICT`.

### POST /volunteer/register/resend
Повторная отправка кода подтверждения. **Публичный.**
- **Тело:** `{ "email": "v@mail.ru" }`
- **200:** `{ "ok": true, "email_sent": false, "already_verified": false, "code_length": 4, "resend_after": 60, "email_verify_code": "..." }`.
- Слишком рано (кулдаун 60 с) → `429 RESEND_TOO_SOON`, `error.details.resend_after` — сек до отправки.

### POST /volunteer/verify-email
Подтверждение почты **кодом**. **Публичный.**
- **Тело:** `{ "email": "v@mail.ru", "code": "3116" }` → **200** `{ "ok": true, "email_verified": true }` (идемпотентно, если уже подтверждён).
- Неверный код → `400 INVALID_CODE`, `error.details.attempts_left` — сколько попыток осталось.
- Исчерпан лимит (5 попыток) → `429 TOO_MANY_ATTEMPTS` (код заблокирован, запросить новый через `register/resend`).
- Код истёк (TTL 15 мин) → `400 CODE_EXPIRED`.

### POST /volunteer/login
Вход. **Публичный.**
- **Тело:** `{ "email", "password" }`
- **200:** `{ "access_token", "token_type": "bearer", "volunteer": { "id","email","phone","email_verified" } }`.
- Почта не подтверждена → `403 EMAIL_NOT_VERIFIED`; заблокирован → `403`; неверные данные → `401`.
- Далее — `Authorization: Bearer <access_token>` для `/volunteer/me` и `/volunteer/onboarding`.

### POST /volunteer/password/reset-request
Запрос восстановления. **Публичный.** Всегда `{ "ok": true }` (анти-энумерация).
- **Тело:** `{ "email" }` → `{ "ok": true, "email_sent": false, "reset_token": "...", "reset_url": "..." }` (токен — только при `email_sent=false` и если волонтёр существует).

### POST /volunteer/password/reset
Новый пароль по токену. **Публичный.**
- **Тело:** `{ "token", "new_password" }` → **200** `{ "ok": true }`. Битый токен → `400`.

### GET /volunteer/me
Профиль текущего волонтёра. **Bearer (volunteer JWT).**
- **200:** `{ "id","email","phone","email_verified" }`.

### PATCH /volunteer/onboarding
Онбординг — телефон. **Bearer (volunteer JWT).**
- **Тело:** `{ "phone": "+79001234567" }` (необяз., ≤32) → профиль волонтёра.

> Справочник волонтёров в админке (`GET /volunteers`, блокировка/удаление) — под ролью `admin`, в мобильный API не входит.

---

<a id="раздел-авторизация"></a>
## 1. Авторизация

### POST /auth/login
Вход по email + паролю.

- **Авторизация:** не требуется.
- **Запрос** (`application/json`):

```json
{ "email": "inspector@ecopulse.ru", "password": "secret123" }
```

- **Ответ 200** — access-токен в теле, refresh — в `HttpOnly`-cookie:

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

- **Примечания:**
  - Неверный email **или** пароль → `401 INVALID_CREDENTIALS` (единый ответ,
    факт существования email не раскрывается — anti-enumeration).
  - 5 неудачных попыток подряд → блокировка на 15 минут: `429 ACCOUNT_LOCKED`
    (сообщение содержит оставшееся время).
  - Заблокированный админом аккаунт (`is_active=false`) при верном пароле →
    `403 USER_INACTIVE`.
  - Клиенту следует хранить `access_token` и подставлять его в заголовок
    `Authorization` для защищённых запросов.

### POST /auth/refresh
Обновление access-токена по refresh-cookie.

- **Авторизация:** не требуется в заголовке; используется cookie `refresh_token`
  (браузер шлёт автоматически; мобильному клиенту нужно сохранять/пересылать cookie).
- **Запрос:** тело не требуется.
- **Ответ 200:**

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

- **Примечания:** отсутствие/просрочка/невалидность refresh-cookie →
  `401 INVALID_CREDENTIALS`. Успешный refresh **ротирует** refresh-cookie (выдаёт новую).

### POST /auth/logout
Выход — удаляет refresh-cookie.

- **Авторизация:** не требуется.
- **Ответ 200:**

```json
{ "message": "Вы вышли из системы" }
```

- **Примечания:** access-токен на сервере не отзывается (stateless JWT) — клиент
  должен удалить его сам. Cookie `refresh_token` очищается.

### GET /auth/me
Текущий пользователь (входит и в раздел «Профиль пользователя»).

- **Авторизация:** Bearer JWT.
- **Ответ 200** (`UserMe`):

```json
{
  "id": "3f2a...-uuid",
  "email": "inspector@ecopulse.ru",
  "fio": "Иванов Иван Иванович",
  "role": "user",
  "status": "active",
  "is_superadmin": false
}
```

- **Поля:** `role` = `admin` | `user`; `status` = `active` | `invited`
  (`invited → active` при первом успешном входе).

---

<a id="раздел-профиль-пользователя"></a>
## 2. Профиль пользователя

Управление собственной учётной записью. Все эндпоинты требуют **Bearer JWT**.

### GET /auth/me
См. [раздел «Авторизация»](#раздел-авторизация) — возвращает `UserMe` текущего
пользователя.

### PATCH /profile
Смена собственного ФИО.

- **Авторизация:** Bearer JWT.
- **Запрос** (`application/json`):

```json
{ "fio": "Петров Пётр Петрович" }
```

- **Ответ 200:** обновлённый `UserMe` (см. `GET /auth/me`).

### POST /profile/password
Смена собственного пароля (без ввода текущего — по ТЗ §9.1).

- **Авторизация:** Bearer JWT.
- **Запрос** (`application/json`):

```json
{ "new_password": "новыйПароль123" }
```

- **Ответ 200:**

```json
{ "message": "Пароль обновлён" }
```

- **Ограничения:** `new_password` — min 6 / max 128 символов; нарушение →
  `422 VALIDATION_ERROR`.

---

<a id="раздел-регионы"></a>
## 3. Регионы

Справочник субъектов РФ и федеральных округов. Все эндпоинты требуют **Bearer JWT**.

### GET /regions
Список регионов с фильтром/сортировкой и агрегатами (кол-во МНО и обращений).

- **Авторизация:** Bearer JWT.
- **Query-параметры:**

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `search` | string | — | подстрока по коду/названию региона |
| `fed` | int (repeatable) | — | фильтр по номеру фед. округа (1..8), можно несколько: `?fed=1&fed=3` |
| `sort` | string | `code` | `code` · `name` · `fed` · `operator` · `mno` · `inc` |
| `order` | string | `asc` | `asc` · `desc` |

- **Ответ 200** — массив `RegionListItem`:

```json
[
  {
    "code": "63",
    "name": "Самарская область",
    "fed": 6,
    "fed_code": "PFO",
    "fed_name": "Приволжский федеральный округ",
    "operators": ["ЭкоСтройРесурс"],
    "active": true,
    "last_sync": null,
    "mno_count": 12,
    "incidents_count": 34
  }
]
```

### GET /regions/{code}
Карточка региона по коду субъекта.

- **Авторизация:** Bearer JWT.
- **Path:** `code` — строковый код субъекта (например `63`).
- **Ответ 200:** объект `RegionDetail` (те же поля, что в списке).
- **Примечания:** несуществующий код → `404 NOT_FOUND`.

### GET /federal-districts
Справочник федеральных округов РФ (нумерация ФГИС 1..8).

- **Авторизация:** Bearer JWT.
- **Ответ 200:**

```json
[
  { "id": 1, "code": "CFO", "name": "Центральный федеральный округ" },
  { "id": 6, "code": "PFO", "name": "Приволжский федеральный округ" }
]
```

> Дополнительно существует `POST /regions` (создание региона, тег «Регионы» в
> Swagger) — административная операция вне основного мобильного сценария;
> дубликат кода → `409 CONFLICT`.

---

<a id="раздел-карта-и-мно"></a>
## 4. Карта и МНО

Реестр мест накопления отходов (МНО). Координаты (`coords`) присутствуют в каждом
элементе — используются для отрисовки на карте. Все эндпоинты требуют **Bearer JWT**.

### GET /mno
Реестр МНО с фильтрами и сортировкой.

- **Авторизация:** Bearer JWT.
- **Query-параметры:**

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `search` | string | — | подстрока по name/reg/city/address/coords/fgis_id |
| `region` | string | — | код субъекта РФ (`region_code`) |
| `synced` | bool | — | `true` — только синхронизированные с ФГИС, `false` — нет |
| `sort` | string | `name` | `name` · `reg` · `region` · `city` · `address` · `coords` |
| `order` | string | `asc` | `asc` · `desc` |
| `bbox` | string | — | видимая область карты/гео `«minLat,minLon,maxLat,maxLon»` — вернуть только МНО этого кадра (ближайшие к точке), как в `/mno/points` |
| `page` | int ≥1 | `1` | номер страницы |
| `page_size` | int 1..200 | `100` | размер страницы |

> **Данные «в зависимости от точки на карте/гео»:** передавайте `bbox` — тогда список
> отдаёт только МНО текущего кадра (площадки рядом с пользователем), а не весь реестр.
> Формат и поведение — как у `/mno/points` (фильтр по числовым координатам). `bbox`
> комбинируется с `region`/`search`; без `bbox` — весь отфильтрованный реестр постранично.
> Чтобы показать ближайшие к геолокации — центрируйте `bbox` на позиции пользователя.
> `incidents` в ответе — живой счётчик обращений, привязанных к этому МНО.

- **Ответ 200** — массив `MnoListItem`:

```json
[
  {
    "id": "a1b2...-uuid",
    "reg": "РЕГ-000123",
    "name": "Контейнерная площадка №5",
    "region_code": "63",
    "region_name": "Самарская область",
    "city": "Самара",
    "address": "ул. Ленина, 10",
    "coords": "53.195, 50.101",
    "fgis_id": null,
    "synced": false,
    "sync_date": null,
    "incidents": 3
  }
]
```

- **Примечания:** `coords` — строка «широта, долгота»; для карты парсится клиентом.
  `incidents` — число привязанных обращений.

### POST /mno/sync
**ЗАГЛУШКА** синхронизации с ФГИС. Помечает все ещё-не-синхронизированные МНО как
синхронизированные (локально, без внешних запросов к ФГИС).

- **Авторизация:** Bearer JWT.
- **Запрос:** тело не требуется.
- **Ответ 200** (`MnoSyncResult`):

```json
{ "synced": 4, "total": 16 }
```

- **Примечания:** `synced` — сколько записей помечено при этом вызове; `total` —
  всего МНО. Реальной интеграции с ФГИС нет — это заглушка (см. `services/mno.py`).

### POST /mno/{id}/sync
**ЗАГЛУШКА** синхронизации одного МНО с ФГИС (без внешних запросов).

- **Авторизация:** Bearer JWT.
- **Path:** `id` — UUID МНО.
- **Ответ 200:** обновлённый объект `MnoDetail` (`synced=true`, проставлен `sync_date`).
- **Примечания:** несуществующий `id` → `404 NOT_FOUND`.

---

<a id="раздел-карточка-мно"></a>
## 5. Карточка МНО

### GET /mno/{id}
Детальная карточка одного МНО.

- **Авторизация:** Bearer JWT.
- **Path:** `id` — UUID МНО.
- **Ответ 200:** объект `MnoDetail` (набор полей идентичен `MnoListItem` из
  [раздела «Карта и МНО»](#раздел-карта-и-мно)).
- **Примечания:** несуществующий `id` → `404 NOT_FOUND`.

---

<a id="раздел-отправка-фотоотчёта"></a>
## 6. Отправка фотоотчёта

### POST /intake/form
Приём обращения из формы волонтёра. Создаёт обращение с `source="form"`.

- **Content-Type:** `multipart/form-data`.
- **Авторизация:** публичный эндпоинт (Bearer **не** требуется). Анти-спам —
  honeypot-поле `website`: если оно непустое, запрос считается ботом — сервер
  возвращает `{ "ok": true }` и **ничего не создаёт**.
- **Поля формы:**

| Поле | Тип | Обяз. | Описание / ограничения |
|---|---|---|---|
| `fio` | text | нет | ФИО заявителя (≤255 симв.) |
| `incident_type` | text | **да** | код типа инцидента из `GET /intake/incident-types` (напр. `fire`); сохраняется, только если код валиден (иначе `null`) |
| `comment` | text | **да** | описание проблемы, свободный текст (в форме обязателен) |
| `region` | text | нет | регион (≤255); если пусто — выводится из `full_address` |
| `city` | text | нет | город/н.п. (≤255) |
| `street` | text | нет | улица/дом (≤500) |
| `full_address` | text | нет | полный адрес одной строкой (fallback для region/city/street) |
| `coords` | text | нет | «широта, долгота» (≤64) |
| `photo_time` | text | нет | время фотофиксации; форматы: `ДД.ММ.ГГГГ, ЧЧ:ММ`, `ДД.ММ.ГГГГ ЧЧ:ММ`, `ГГГГ-ММ-ДД ЧЧ:ММ` или ISO 8601; иначе игнорируется |
| `bins` | text | нет | наличие баков: `да`/`yes`/`true` → true, `нет`/`no`/`false` → false, иначе null |
| `website` | text | нет | **honeypot** — должно быть пустым (для людей) |
| `photos` | file (repeatable) | нет | 1..3 фото; jpg/png/webp; каждый ≤10 МБ |

- **Ответ 200** (успешный приём):

```json
{
  "ok": true,
  "incident_id": "d4e5...-uuid",
  "quote": "Природа не знает остановки в своём движении и казнит всякое бездействие."
}
```

- **Ответ 200** (сработал honeypot): `{ "ok": true }` (обращение не создаётся).
- **Примечания:**
  - Фото **валидируются и пере-кодируются** сервером в JPEG: полноразмер `{i}.jpg`
    (до 1600 px по большей стороне) + превью `{i}_thumb.jpg` (до 400 px). Возвращаемые
    `photo_urls` инцидента указывают на `GET /intake/photo/...` (см.
    [раздел «Загрузка фото»](#раздел-загрузка-фото)).
  - Битый/не-изображение / файл >10 МБ / более 3 фото → `400 VALIDATION_ERROR`
    (запись в БД не создаётся).
  - `quote` — мотивирующая цитата о природе; генерируется best-effort после сохранения
    (может отсутствовать, если генератор недоступен).
  - **Замечание о токене:** в текущей реализации `POST /intake/form` заголовок
    `X-Intake-Token` **не проверяет** — это публичная форма, защищённая honeypot-ом.
    Заголовок `X-Intake-Token` требуется только для server-to-server вебхуков
    (`/intake/yandex`, `/intake/max` и очереди уведомлений), которые в мобильный API
    не входят.

### GET /intake/incident-types
Справочник типов инцидента — для дропдауна «Тип инцидента» в форме отчёта. **Публичный**
(Bearer не требуется). Список ведётся в админке (редактируемый справочник), поэтому запрашивайте
его с сервера — **не хардкодьте**.

- **Ответ 200** — массив `{ code, label }` в порядке отображения:

```json
[
  { "code": "no_access", "label": "Отсутствует доступ к МНО" },
  { "code": "fire", "label": "Возгорание в контейнере" },
  { "code": "other", "label": "Иное" }
]
```

- `code` — отправляется в поле `incident_type` при `POST /intake/form`; `label` — подпись для UI.
- Редактирование справочника (`POST`/`PATCH`/`DELETE /incident-types`) — только роль `admin` (веб-админка), в мобильный API не входит.

---

<a id="раздел-добавление-нового-мно"></a>
## 7. Добавление нового МНО

### POST /mno
Ручное создание записи МНО.

- **Авторизация:** Bearer JWT.
- **Запрос** (`application/json`):

```json
{
  "name": "Контейнерная площадка №7",
  "coords": "53.201, 50.145",
  "reg": "",
  "region_code": "63",
  "city": "Самара",
  "address": "ул. Победы, 22"
}
```

- **Обязательные поля:** `name` (min 1) и `coords` (min 1). Остальные (`reg`,
  `region_code`, `city`, `address`) необязательны (по умолчанию пустая строка).
- **Ответ 201** — созданный объект `MnoDetail`. Сервис проставляет `synced=false`,
  `fgis_id=null`, `incidents=0` (эти поля из тела **не** принимаются).
- **Примечания:** отсутствие `name`/`coords` или пустые значения → `422 VALIDATION_ERROR`.

---

<a id="раздел-загрузка-фото"></a>
## 8. Загрузка фото

### GET /intake/photo/{incident_id}/{filename}
Публичная отдача байтов фото обращения.

- **Авторизация:** не требуется (публично).
- **Path:**
  - `incident_id` — UUID обращения;
  - `filename` — строго `^[0-9]+(_thumb)?\.jpg$`:
    - полноразмер: `0.jpg`, `1.jpg`, `2.jpg`;
    - превью: `0_thumb.jpg`, `1_thumb.jpg`, `2_thumb.jpg`.
- **Ответ 200:** тело — `image/jpeg` (заголовки `Content-Disposition: inline`,
  `X-Content-Type-Options: nosniff`).
- **Примечания:**
  - Жёсткий анти-traversal: невалидный UUID, имя вне шаблона или выход за пределы
    каталога → `404 NOT_FOUND`; отсутствующий файл → `404 NOT_FOUND`.
  - **Загрузка** фото выполняется не здесь, а внутри `multipart POST /intake/form`
    (поле `photos[]`); этот эндпоинт только отдаёт уже сохранённые файлы. URL-ы
    доступных фото приходят в поле `photo_urls` элементов обращения.

### GET /intake/suggest/address
Подсказки адреса (DaData) для автозаполнения формы волонтёра.

- **Авторизация:** не требуется (публично; ключ DaData остаётся на сервере).
- **Query-параметры:**

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `q` | string | `""` | строка запроса; при длине < 3 символов возвращается пустой список |
| `kind` | string | `full` | уровень: `region` · `city` · `street` · `full` |
| `region` | string | — | ограничение по региону (для `kind=city`/`street`) |
| `city` | string | — | ограничение по городу (для `kind=street`) |
| `count` | int | `8` | число подсказок (обрезается до диапазона 1..15) |

- **Ответ 200:**

```json
{ "suggestions": [ { "value": "г Самара, ул Ленина, д 10", "data": { "geo_lat": "53.19", "geo_lon": "50.10" } } ] }
```

- **Примечания:** без ключа DaData / при `q` < 3 символов / при сбое DaData возвращается
  `{ "suggestions": [] }` (форма деградирует до ручного ввода).

---

<a id="раздел-админский-реестр"></a>
## 9. Админский реестр

Работа с обращениями (инцидентами). Все эндпоинты требуют **Bearer JWT**.

### GET /incidents
Список обращений с фильтрами, сортировкой и пагинацией.

- **Авторизация:** Bearer JWT.
- **Query-параметры:**

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `search` | string | — | подстрока (ФИО/адрес/…) |
| `source` | string (repeatable) | — | источник: `max` · `form` (можно несколько) |
| `status` | string (repeatable) | — | статус: `new` · `found` · `none` · `exported` |
| `region` | string | — | фильтр по региону |
| `incident_type` | string | — | фильтр по коду типа инцидента (коды — из `GET /intake/incident-types`) |
| `date_from` | date (`ГГГГ-ММ-ДД`) | — | нижняя граница периода (по фотофиксации) |
| `date_to` | date (`ГГГГ-ММ-ДД`) | — | верхняя граница периода |
| `sort` | string | `date` | `date` · `time` · `region` · `city` · `address` · `status` · `source` |
| `order` | string | `desc` | `asc` · `desc` |
| `page` | int ≥1 | `1` | номер страницы |
| `page_size` | int 1..200 | `100` | размер страницы |

- **Ответ 200** (`Paginated[IncidentListItem]`):

```json
{
  "items": [
    {
      "id": "d4e5...-uuid",
      "source": "form",
      "status": "new",
      "fio": "Иванов И.И.",
      "region": "Самарская область",
      "city": "Самара",
      "street": "ул. Ленина, 10",
      "coords": "53.195, 50.101",
      "comment": null,
      "incident_type": "fire",
      "photo_time": "2026-06-25T14:30:00+00:00",
      "photos": 2,
      "photo_urls": [
        "/api/v1/intake/photo/d4e5...-uuid/0.jpg",
        "/api/v1/intake/photo/d4e5...-uuid/1.jpg"
      ],
      "msg": null,
      "msg_url": null,
      "received_at": "2026-06-25T14:35:10+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 100,
  "pages": 1
}
```

### GET /incidents/funnel
Счётчики воронки статусов. Учитывают `search`/`source`/`region`/период, но **не**
`status` (чтобы показать распределение по всем статусам при текущем фильтре).

- **Авторизация:** Bearer JWT.
- **Query-параметры:** `search`, `source[]`, `region`, `date_from`, `date_to`
  (как в `GET /incidents`).
- **Ответ 200** (`FunnelCounts`):

```json
{ "all": 120, "new": 40, "found": 30, "none": 20, "exported": 30 }
```

### GET /incidents/regions
DISTINCT непустые названия регионов, встречающихся в обращениях (А→Я) — наполняет
дропдаун фильтра региона.

- **Авторизация:** Bearer JWT.
- **Ответ 200:** массив строк, например `["Московская область", "Самарская область"]`.

### GET /incidents/{id}
Карточка обращения (включает `bins`, `created_at`, `updated_at`).

- **Авторизация:** Bearer JWT.
- **Path:** `id` — UUID обращения.
- **Ответ 200** (`IncidentDetail`): все поля `IncidentListItem` плюс `bins`
  (`true`/`false`/`null`), `created_at`, `updated_at`.
- **Примечания:** несуществующий `id` → `404 NOT_FOUND`.

### PATCH /incidents/{id}/status
Смена статуса одного обращения.

- **Авторизация:** Bearer JWT.
- **Path:** `id` — UUID обращения.
- **Запрос** (`application/json`):

```json
{ "status": "found" }
```

- **Допустимые значения `status`:** `new` · `found` · `none` · `exported`.
- **Ответ 200:** обновлённый `IncidentDetail`.
- **Примечания:** недопустимый статус → `422 VALIDATION_ERROR`; несуществующий `id`
  → `404 NOT_FOUND`. Изменение фиксируется в audit-логе.

### POST /incidents/bulk-status
Массовая смена статуса.

- **Авторизация:** Bearer JWT.
- **Запрос** (`application/json`):

```json
{ "ids": ["uuid-1", "uuid-2"], "status": "exported" }
```

- **Ответ 200** (`BulkStatusResult`):

```json
{ "updated": 2 }
```

### POST /incidents/bulk-delete
Массовое удаление обращений (hard delete, каждое пишется в audit-лог).

- **Авторизация:** Bearer JWT.
- **Запрос** (`application/json`):

```json
{ "ids": ["uuid-1", "uuid-2"] }
```

- **Ответ 200** (`BulkDeleteResult`):

```json
{ "deleted": 2 }
```

---

<a id="раздел-ошибки"></a>
## 10. Ошибки

Все ошибки возвращаются единым конвертом:

```json
{ "error": { "code": "<КОД>", "message": "<человекочитаемо>", "details": <null | object | array> } }
```

Для ошибок валидации тела/параметров (`422`) `details` — список полей:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Ошибка валидации данных",
    "details": [ { "field": "body.new_password", "message": "String should have at least 6 characters" } ]
  }
}
```

### Типовые коды (реальные, из `app/core/errors.py`)

| HTTP | `code` | Когда возникает |
|---|---|---|
| 400 | `VALIDATION_ERROR` | бизнес-валидация: битое/не-изображение фото, пустой файл, файл > 10 МБ, более 3 фото, некорректный JSON вебхука |
| 401 | `INVALID_CREDENTIALS` | неверный email/пароль; неизвестный email (anti-enumeration); невалидный/просроченный/не-того-типа access- или refresh-токен; пользователь из токена не найден |
| 401 | `NOT_AUTHENTICATED` | отсутствует/некорректен заголовок `Authorization: Bearer …` на защищённом эндпоинте |
| 403 | `USER_INACTIVE` | учётная запись деактивирована админом (`is_active=false`) при верном пароле/токене |
| 403 | `FORBIDDEN` | недостаточно прав (например, требуется роль `admin`); неверный `X-Intake-Token` на server-to-server эндпоинте |
| 404 | `NOT_FOUND` | сущность не найдена (обращение, МНО, регион, фото, пользователь) |
| 409 | `CONFLICT` | конфликт уникальности: дубликат email при создании пользователя; дубликат кода региона при создании региона |
| 422 | `VALIDATION_ERROR` | ошибка схемы запроса (Pydantic): неверный тип/формат, невалидный email, длина пароля вне 6..128, недопустимый `status`/`sort`/`order` и т.п.; `details` — список `{field, message}` |
| 429 | `ACCOUNT_LOCKED` | вход заблокирован после 5 неудачных попыток на 15 минут (`message` содержит оставшееся время) |
| 503 | `INTAKE_DISABLED` | приём server-to-server отключён (не задан `X-Intake-Token` на сервере) — относится к вебхукам, вне мобильного API |

Непредвиденная ошибка сервера → `500 INTERNAL_ERROR`
(`message` = «Внутренняя ошибка сервера», `details = null`).

---

## Приложение: справочник схем

| Схема | Поля |
|---|---|
| `UserMe` | `id`, `email`, `fio`, `role`(`admin`\|`user`), `status`(`active`\|`invited`), `is_superadmin` |
| `TokenResponse` | `access_token`, `token_type`(=`bearer`) |
| `RegionListItem` / `RegionDetail` | `code`, `name`, `fed`, `fed_code`, `fed_name`, `operators[]`, `active`, `last_sync`, `mno_count`, `incidents_count` |
| `FederalDistrict` | `id`, `code`, `name` |
| `MnoListItem` / `MnoDetail` | `id`, `reg`, `name`, `region_code`, `region_name`, `city`, `address`, `coords`, `fgis_id`, `synced`, `sync_date`, `incidents` |
| `MnoSyncResult` | `synced`, `total` |
| `IncidentListItem` | `id`, `source`(`max`\|`form`), `status`(`new`\|`found`\|`none`\|`exported`), `fio`, `region`, `city`, `street`, `coords`, `comment`, `photo_time`, `photos`, `photo_urls[]`, `msg`, `msg_url`, `received_at` |
| `IncidentDetail` | поля `IncidentListItem` + `bins`, `created_at`, `updated_at` |
| `FunnelCounts` | `all`, `new`, `found`, `none`, `exported` |
| `Paginated[T]` | `items[]`, `total`, `page`, `page_size`, `pages` |

> Полный контракт со схемами и примерами — [`contracts/openapi.json`](../contracts/openapi.json),
> интерактивно — Swagger UI по адресу `/docs`, ReDoc — `/redoc`.
