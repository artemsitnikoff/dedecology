# Развёртывание ЭкоПульс на сервере

Цель: поднять приложение на **`http://<SERVER_IP>:8888`** (заход по IP, без домена).
Открыт наружу только порт **8888**; `backend` и `postgres` доступны лишь внутри docker-сети,
nginx фронта проксирует `/api/` → `backend:8000` (всё одного origin, без CORS).

> Завтра добавим домен + HTTPS (см. §6) — тогда `SESSION_COOKIE_SECURE=True`.

---

## 0. Что нужно на сервере (один раз)
- Ubuntu/Debian (или любой Linux), доступ по SSH, **root/sudo**.
- **Docker + плагин compose**. Проверка: `docker --version` и `docker compose version`.
  Если нет — установить:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER     # затем перелогиниться (exit + заново ssh)
  ```
- **git**: `sudo apt-get update && sudo apt-get install -y git`.

## 1. Клонировать репозиторий
```bash
sudo mkdir -p /var/www && cd /var/www
git clone https://github.com/artemsitnikoff/dedecology.git
cd dedecology
```

## 2. Создать и заполнить `.env`
```bash
cp .env.example .env
nano .env          # (или vim)
```
Обязательно поменять/проверить:
- `POSTGRES_PASSWORD` — задать СВОЙ длинный пароль.
- `DATABASE_URL` — **тот же пароль**, что в `POSTGRES_PASSWORD` (формат
  `postgresql+asyncpg://dedecolog:<ТОТ_ЖЕ_ПАРОЛЬ>@db:5432/dedecolog`).
- `JWT_SECRET` — сгенерировать: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
  (или `openssl rand -base64 48`), вставить.
- `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` — логин/пароль первого админа (под ним зайдёшь).
- `CORS_ORIGINS=http://<SERVER_IP>:8888` — подставить реальный IP сервера.
- `VITE_API_BASE_URL=/api/v1` — **оставить как есть** (относительный путь, проксируется nginx).
- `SESSION_COOKIE_SECURE=False` — **оставить False** (заход по HTTP/IP). На HTTPS поменяем.

## 3. Поднять (БД → миграции → сид → всё)
```bash
# 1) База
docker compose -f docker-compose.prod.yml up -d --build db

# 2) Схема БД
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 3) Сид: админ + 2 демо-пользователя + 13 демо-инцидентов
docker compose -f docker-compose.prod.yml run --rm backend python -m app.seed

# 4) Поднять backend + frontend (frontend соберётся с VITE_API_BASE_URL из .env)
docker compose -f docker-compose.prod.yml up -d --build
```
Проверить, что всё running:
```bash
docker compose -f docker-compose.prod.yml ps
```

## 4. Открыть порт 8888
- **ufw** (если включён): `sudo ufw allow 8888/tcp`
- **Облачный провайдер** (Selectel/Yandex/Timeweb/AWS…): открыть **TCP 8888** в Security Group /
  firewall панели — это отдельно от ufw, часто именно тут блок.

## 5. Проверить
- В браузере: **`http://<SERVER_IP>:8888`** → экран входа → залогиниться
  `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`.
- API жив: `curl http://<SERVER_IP>:8888/api/v1/auth/me` → должен вернуть 401 (это нормально без токена — значит проксирование работает).
- Логи если что-то не так:
  ```bash
  docker compose -f docker-compose.prod.yml logs -f backend
  docker compose -f docker-compose.prod.yml logs -f frontend
  ```

---

## 6. Домен + HTTPS (dedecology.ru) — открывать без :8888
Код УЖЕ готов к домену: `VITE_API_BASE_URL=/api/v1` — относительный, фронт работает на любом хосте,
**пересобирать фронт НЕ нужно**. Нужны: реверс-прокси с TLS на хосте + 2 флага в `.env`.

1. **DNS:** A-запись `dedecology.ru` → `5.253.228.219` (+ `www`). IPv6 нет → только A. Дождись пропагации.
2. **Caddy на хосте** (авто Let's Encrypt) — `/etc/caddy/Caddyfile`:
   ```
   dedecology.ru, www.dedecology.ru {
       reverse_proxy 127.0.0.1:8888
   }
   ```
   `sudo systemctl reload caddy`. Caddy сам выпустит сертификат (нужны открытые 80 и 443).
   (Альтернатива — nginx + certbot, server-блок с `proxy_pass http://127.0.0.1:8888;`.)
3. **`.env`** (бэк за HTTPS) — `cd /var/www/dedecology`:
   ```
   sed -i 's/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=True/' .env
   sed -i 's#^CORS_ORIGINS=.*#CORS_ORIGINS=https://dedecology.ru,https://www.dedecology.ru#' .env
   docker compose -f docker-compose.prod.yml up -d backend
   ```
   `VITE_API_BASE_URL=/api/v1` НЕ трогать (фронт не пересобирать).
4. **Закрыть публичный :8888** (наружу теперь только Caddy 443): в `docker-compose.prod.yml` у `frontend`
   `ports: ["8888:80"]` → `["127.0.0.1:8888:80"]`, затем `docker compose -f docker-compose.prod.yml up -d frontend`.
5. **Firewall:** `sudo ufw allow 80,443/tcp` (+ облачный SG); 8888 можно закрыть.

**Проверка:** `https://dedecology.ru` грузится, вход держится (Secure-cookie), `https://dedecology.ru/form`.
⚠️ С `SESSION_COOKIE_SECURE=True` вход по голому `http://…:8888` сессию держать перестанет — заходи по https-домену.

---

## 6.5 CI/CD — авто-деплой на push в main (как у glafira)
В репозитории есть `.github/workflows/deploy.yml`. Каждый push в `main` (или ручной запуск во
вкладке **Actions → Deploy to VPS → Run workflow**) идёт по SSH на сервер, делает `git pull --ff-only`,
пересобирает **только изменившуюся часть** (backend/frontend), `docker compose ... up -d`, и
`alembic upgrade head` — только если менялись файлы миграций. Сид НЕ запускается (только вручную).

**Настроить один раз:**
1. Сначала пройди ПЕРВЫЙ деплой вручную (§1–§5): репо склонировано в `/var/www/dedecology`, `.env`
   заполнен, контейнеры подняты. CI обслуживает только последующие пуши.
2. Сгенерировать deploy-ключ и положить публичный на сервер:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/dedecolog_deploy -N "" -C "dedecolog-ci"
   ssh-copy-id -i ~/.ssh/dedecolog_deploy.pub <SSH_USER>@<SERVER_IP>
   ```
3. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**:
   - `SSH_HOST` = IP сервера
   - `SSH_USER` = пользователь (владелец `/var/www/dedecology`, с доступом к docker)
   - `SSH_PRIVATE_KEY` = весь приватный ключ `~/.ssh/dedecolog_deploy`
   - (опц.) `SSH_PORT` — если SSH не на 22; тогда раскомментируй строку `port:` в `deploy.yml`
4. Клонировал не в `/var/www/dedecology`? Поправь путь `cd ...` в `deploy.yml`.
5. Проверка: вкладка **Actions** → **Deploy to VPS** → **Run workflow** (или просто push в main).

> ⚠️ Файл `.github/workflows/*` пушится только токеном со scope **`workflow`**. Если `git push`
> отбил его (`refusing to allow ... workflow scope`) — обнови токен `gh auth refresh -s workflow`
> и повтори push, либо добавь файл через веб-интерфейс GitHub (Add file → Create new file).

---

## 7. Эксплуатация
**Обновить вручную** (с настроенным CI/CD §6.5 это происходит само на push в main):
```bash
cd /var/www/dedecology
git pull
docker compose -f docker-compose.prod.yml up -d --build
# если в обновлении были миграции БД:
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```
**Рестарт / стоп:**
```bash
docker compose -f docker-compose.prod.yml restart
docker compose -f docker-compose.prod.yml down          # остановить (данные БД сохраняются в volume)
```
**Бэкап БД:**
```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U dedecolog dedecolog | gzip > backup_$(date +%F).sql.gz
```
**Пересоздать сид (осторожно — он идемпотентен, существующее не трёт):**
```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m app.seed
```

## 8. Если не открывается
- `docker compose -f docker-compose.prod.yml ps` — все контейнеры `Up`/`healthy`?
- Порт 8888 открыт И в ufw, И в облачном firewall? (частая причина — облачный SG).
- `... logs backend` — нет ошибок подключения к БД? (проверь, что `DATABASE_URL` пароль == `POSTGRES_PASSWORD`).
- 502 на `/api/...` — либо backend ещё поднимается/упал (`... logs backend`), ЛИБО фронт-nginx
  закэшировал старый IP backend после его пересоздания → `docker compose -f docker-compose.prod.yml
  restart frontend` (nginx перечитает адрес). Деплой (§6.5) теперь пересоздаёт frontend сам.
- Логин не держится / сразу разлогинивает — убедись, что `SESSION_COOKIE_SECURE=False` при заходе по HTTP.

## 9. Бэкап БД
Скрипты в `scripts/` (приезжают на сервер через `git pull`), запускать на VPS из `/var/www/dedecology`:
```bash
# сделать бэкап (pg_dump -Fc → backups/dedecolog_<дата>.dump, ротация — 14 последних)
bash scripts/backup-db.sh

# восстановить из дампа (⚠️ перезапишет данные, спросит подтверждение)
bash scripts/restore-db.sh backups/dedecolog_ГГГГММДД_ЧЧММСС.dump
```
- Дампы лежат в `backups/` (исключён из git — внутри ПДн). Скопируй их с сервера в надёжное место
  (`scp`/облако) — на том же диске это НЕ резервная копия.
- Авто-расписание (ежедневно 3:30) — добавь в `crontab -e`:
  `30 3 * * * bash /var/www/dedecology/scripts/backup-db.sh >> /var/www/dedecology/backups/backup.log 2>&1`

## 10. Синхронизация ФГИС УТКО (раздел «Интеграция») — эксплуатация и разбор «висит»
Фоновый краул МНО исполняет сервис `worker` (arq), прогресс — в Redis, запуск/отмена — из UI
(супер-админ, `/integration`).

**Смотреть вживую:**
```bash
docker compose -f docker-compose.prod.yml logs -f worker
```
Пишется КАЖДЫЙ батч (`[mno_worker] регион N батч #K [ok|timeout|error]: … | X.Xс`) и ход обхода
каждые 25 раундов (`[fgis] обход: раунд R … обнаружено X из ~Y`). Тишина после старта задачи =
логи приложения заглушены → воркер на СТАРОМ коде (см. ниже про force-recreate).

**Как устроено (чтобы не гадать при «висит/долго»):**
- Обход стоп, как только `обнаружено >= итог региона` (ФГИС даёт итог суммой `iconContent` на
  грубом зуме) — уже собранный регион НЕ домалывается вхолостую (иначе очередь растёт часами).
- На каждый батч деталей — таймаут `DETAIL_TIMEOUT=120с`: ФГИС молчит → батч `[timeout]`,
  пропускается (доберётся при повторе), синк идёт дальше. **Вечно висеть не может.**
- Сбой батча (сеть/длина поля) → `session.rollback()` + пропуск, регион не падает каскадом.
- Возобновление дешёвое: уже записанные МНО (по `fgis_id`) пропускаются (счётчик `skipped`).

**Убить очередь / зависшую задачу** (данные в Postgres и маркеры `region_synced` НЕ трогаем):
```bash
docker compose -f docker-compose.prod.yml exec redis sh -c 'redis-cli del arq:queue; for k in $(redis-cli --scan --pattern "mno:ptr:*") $(redis-cli --scan --pattern "mno:cancel:*") $(redis-cli --scan --pattern "arq:job:*"); do redis-cli del "$k"; done; echo cleared'
docker compose -f docker-compose.prod.yml restart worker    # добьёт КРУТЯЩУЮСЯ задачу
```
⚠️ НЕ `flushall` — снесёт `mno:region_synced:*` (маркеры собранных регионов) и внутренности arq.

**Грабли: worker может крутить СТАРЫЙ код.** `worker` переиспользует образ `dedecology-backend:latest`
(без своего `build:`), а `docker compose up -d` не всегда пересоздаёт его под свежесобранный образ.
Деплой (§6.5) теперь форсит это сам (`up -d --force-recreate --no-deps worker frontend` при смене
backend). Вручную:
```bash
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --force-recreate backend worker frontend
docker compose -f docker-compose.prod.yml exec worker grep -c region_total app/services/fgis.py  # ≥1 = новый код
```
