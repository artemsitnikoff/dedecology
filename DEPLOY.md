# Развёртывание ДедЭколог на сервере

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

## 6. Завтра: домен + HTTPS
Когда DNS домена будет указывать на IP сервера — самый простой путь, **Caddy** (авто-Let's Encrypt),
перед контейнером фронта. Кратко:
1. Поменять публикацию фронта на внутренний порт (например `127.0.0.1:8080:80` вместо `8888:80`)
   ИЛИ оставить 8888 и проксировать на него.
2. Поставить Caddy на хосте, `Caddyfile`:
   ```
   dedekolog.example.ru {
       reverse_proxy 127.0.0.1:8080
   }
   ```
   (Caddy сам получит TLS-сертификат.)
3. В `.env`: `SESSION_COOKIE_SECURE=True`, `CORS_ORIGINS=https://dedekolog.example.ru`.
   `VITE_API_BASE_URL=/api/v1` оставить.
4. Пересобрать фронт: `docker compose -f docker-compose.prod.yml up -d --build frontend`.
> Альтернатива Caddy — nginx на хосте + `certbot`. Скажи — распишу под выбранный вариант.

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
- 502 на `/api/...` — backend ещё поднимается или упал; смотри его логи.
- Логин не держится / сразу разлогинивает — убедись, что `SESSION_COOKIE_SECURE=False` при заходе по HTTP.
</content>
