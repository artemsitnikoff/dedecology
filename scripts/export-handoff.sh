#!/usr/bin/env bash
#
# Экспорт данных ЭкоПульс для ПЕРЕДАЧИ хостингу (разворачивают у себя): дамп БД + архив
# файлов (фото инцидентов/МНО + отчёты + логи). Готовит один комплект в handoff/.
#
# Запуск на НАШЕМ сервере (сервисы db и backend должны быть подняты):
#   bash /var/www/dedecology/scripts/export-handoff.sh
#
# Результат в handoff/:
#   • dedecology_db_ГГГГММДД_ЧЧММСС.dump       — pg_dump -Fc (restore через pg_restore)
#   • dedecology_storage_ГГГГММДД_ЧЧММСС.tgz   — содержимое /app/storage (incidents/ mno/ reports/ logs/)
#   • SHA256SUMS.txt                           — контрольные суммы
#   • README-IMPORT.txt                        — инструкция импорта для принимающей стороны
#
# ⚠️ Файлы содержат ПДн (ФИО/адреса/фото) → передавать по защищённому каналу; handoff/ в git не коммитим.
#
# Параметры через env (необязательно):
#   COMPOSE_FILE=docker-compose.prod.yml  DB_SERVICE=db  APP_SERVICE=backend  OUT_DIR=<путь>
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
APP_SERVICE="${APP_SERVICE:-backend}"
OUT_DIR="${OUT_DIR:-$ROOT/handoff}"

STAMP="$(date +%Y%m%d_%H%M%S)"
DB_OUT="$OUT_DIR/dedecology_db_${STAMP}.dump"
ST_OUT="$OUT_DIR/dedecology_storage_${STAMP}.tgz"

mkdir -p "$OUT_DIR"

# --- 1) Дамп БД (pg_dump -Fc внутри контейнера db; креды из его env POSTGRES_*) ---
echo "→ [1/3] Дамп БД через сервис '$DB_SERVICE' ($COMPOSE_FILE)…"
if ! docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -c \
      'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges' \
      > "$DB_OUT"; then
  echo "✗ Ошибка дампа БД — удаляю неполный файл" >&2
  rm -f "$DB_OUT"
  exit 1
fi
[ -s "$DB_OUT" ] || { echo "✗ Пустой дамп БД — удаляю" >&2; rm -f "$DB_OUT"; exit 1; }
echo "  ✓ $DB_OUT ($(du -h "$DB_OUT" | cut -f1))"

# --- 2) Архив файлов из /app/storage (фото + отчёты + логи) ---
# tar стримим ИЗ работающего контейнера backend (не зависим от имени volume).
echo "→ [2/3] Архив /app/storage через сервис '$APP_SERVICE'…"
if ! docker compose -f "$COMPOSE_FILE" exec -T "$APP_SERVICE" \
      tar czf - -C /app/storage . > "$ST_OUT"; then
  echo "✗ Ошибка архивации storage — удаляю неполный файл" >&2
  rm -f "$ST_OUT"
  exit 1
fi
[ -s "$ST_OUT" ] || { echo "✗ Пустой архив storage — удаляю" >&2; rm -f "$ST_OUT"; exit 1; }
echo "  ✓ $ST_OUT ($(du -h "$ST_OUT" | cut -f1))"

# --- 3) Контрольные суммы + инструкция импорта ---
echo "→ [3/3] Контрольные суммы + README-IMPORT.txt…"
( cd "$OUT_DIR" && sha256sum "$(basename "$DB_OUT")" "$(basename "$ST_OUT")" > SHA256SUMS.txt )

cat > "$OUT_DIR/README-IMPORT.txt" <<EOF
ЭкоПульс — импорт переданных данных (БД + файлы). Комплект от $STAMP.

В комплекте:
  • $(basename "$DB_OUT")     — дамп PostgreSQL (custom-формат pg_dump -Fc)
  • $(basename "$ST_OUT") — архив каталога хранилища /app/storage
  • SHA256SUMS.txt              — сверьте: sha256sum -c SHA256SUMS.txt

Проверка целостности перед импортом:
  sha256sum -c SHA256SUMS.txt

------------------------------------------------------------------------
1) БАЗА ДАННЫХ (PostgreSQL 16)
------------------------------------------------------------------------
Восстановление ПЕРЕЗАПИШЕТ данные в целевой БД. Вариант через ваш контейнер БД
(подставьте свои POSTGRES_USER/POSTGRES_DB):

  docker compose exec -T db sh -c \\
    'PGPASSWORD="\$POSTGRES_PASSWORD" pg_restore -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" \\
       --clean --if-exists --no-owner --no-privileges' \\
    < $(basename "$DB_OUT")

Затем накатите миграции (на случай, если ваша схема свежее дампа — идемпотентно):
  docker compose exec -T backend alembic upgrade head

------------------------------------------------------------------------
2) ФАЙЛЫ (фото инцидентов/МНО + отчёты + логи)
------------------------------------------------------------------------
Структура архива (от корня /app/storage):
  incidents/<id>/<n>.jpg   — фото инцидентов (+ _thumb.jpg миниатюры)
  mno/<id>/<i>.jpg         — фото волонтёрских МНО (+ миниатюры)
  reports/<id>.xlsx        — сформированные выгрузки
  logs/                    — логи (операционные; при желании можно не переносить)

Распаковать в каталог/volume, смонтированный в /app/storage контейнера backend:
  # если storage — docker volume (имя вида <project>_backend_storage):
  docker run --rm -i -v <project>_backend_storage:/data alpine \\
    sh -c 'tar xzf - -C /data' < $(basename "$ST_OUT")
  # либо в bind-mount каталог хоста (в т.ч. смонтированный на S3 через rclone — см. ниже):
  tar xzf $(basename "$ST_OUT") -C /srv/<ваш-путь-storage>

ВАЖНО про S3: приложение работает с ФАЙЛОВОЙ СИСТЕМОЙ и НЕ обращается к S3 напрямую —
в URL фото S3 не фигурирует. Чтобы фото физически лежали в S3, смонтируйте бакет в
подкаталоги storage/incidents и storage/mno (rclone mount / s3fs) — тогда распаковка
архива в эти каталоги зальёт фото в S3 прозрачно для приложения. Полная процедура и
переменные — в репозитории: DEPLOY.md §11.

Права: файлы должны быть доступны пользователю, под которым пишет контейнер backend
(при S3-mount — флаги --allow-other + perms/umask, см. DEPLOY.md §11.3).
EOF

echo "✓ Готово. Передайте из $OUT_DIR/:"
echo "    $(basename "$DB_OUT")"
echo "    $(basename "$ST_OUT")"
echo "    SHA256SUMS.txt"
echo "    README-IMPORT.txt"
echo "⚠️  Внутри ПДн — передавайте по защищённому каналу."
