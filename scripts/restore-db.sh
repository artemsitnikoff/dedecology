#!/usr/bin/env bash
#
# Восстановление БД ЭкоПульс из дампа (pg_dump -Fc). ⚠️ ПЕРЕЗАПИСЫВАЕТ текущие данные.
#
# Запуск на сервере:
#   bash /var/www/dedecology/scripts/restore-db.sh backups/dedecolog_ГГГГММДД_ЧЧММСС.dump
#
# Параметры через env: COMPOSE_FILE=docker-compose.prod.yml  DB_SERVICE=db
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
DUMP="${1:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "Использование: bash scripts/restore-db.sh <путь к .dump>" >&2
  echo "Доступные дампы:" >&2
  ls -1t "$ROOT"/backups/dedecolog_*.dump 2>/dev/null >&2 || echo "  (нет в backups/)" >&2
  exit 1
fi

echo "⚠️  Восстановление ПЕРЕЗАПИШЕТ данные в БД (контейнер '$DB_SERVICE')."
echo "    Файл: $DUMP"
read -r -p "Точно продолжить? введите 'yes': " ans
[ "$ans" = "yes" ] || { echo "Отмена."; exit 1; }

# pg_restore внутри контейнера; дамп подаём в stdin с хоста.
# --clean --if-exists — дропает существующие объекты перед заливкой (идемпотентно).
docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
  < "$DUMP"

echo "✓ Восстановление завершено из $DUMP"
