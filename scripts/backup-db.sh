#!/usr/bin/env bash
#
# Бэкап БД ЭкоПульс (PostgreSQL 16 в docker).
#
# Запуск на сервере (из любого каталога):
#   bash /var/www/dedecology/scripts/backup-db.sh
#
# Что делает:
#   • pg_dump ВНУТРИ контейнера `db` (креды берутся из его же env POSTGRES_*);
#   • сжатый custom-формат (-Fc) → backups/dedecolog_ГГГГММДД_ЧЧММСС.dump рядом с репо;
#   • ротация: хранит последние $KEEP дампов, старые удаляет.
#
# Дампы содержат ПДн (ФИО/адреса) → каталог backups/ исключён из git (.gitignore).
# Восстановление — scripts/restore-db.sh.
#
# Параметры через env (необязательно):
#   COMPOSE_FILE=docker-compose.prod.yml  DB_SERVICE=db  KEEP=14  BACKUP_DIR=<путь>
#
# Авто-расписание (пример — ежедневно в 3:30, добавить в `crontab -e`):
#   30 3 * * * bash /var/www/dedecology/scripts/backup-db.sh >> /var/www/dedecology/backups/backup.log 2>&1
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${KEEP:-14}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/dedecolog_${STAMP}.dump"

echo "→ Дамп БД через сервис '$DB_SERVICE' ($COMPOSE_FILE)…"

# pg_dump внутри контейнера; -Fc — сжатый custom-формат (restore через pg_restore),
# -T — без TTY (нужно для редиректа stdout в файл на хосте).
if ! docker compose -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -c \
      'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges' \
      > "$OUT"; then
  echo "✗ Ошибка дампа — удаляю неполный файл" >&2
  rm -f "$OUT"
  exit 1
fi

# Дамп не должен быть пустым.
if [ ! -s "$OUT" ]; then
  echo "✗ Получился пустой дамп — удаляю" >&2
  rm -f "$OUT"
  exit 1
fi

echo "✓ Готово: $OUT ($(du -h "$OUT" | cut -f1))"

# Ротация: оставляем $KEEP свежих, остальные удаляем.
mapfile -t OLD < <(ls -1t "$BACKUP_DIR"/dedecolog_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))")
for f in "${OLD[@]:-}"; do
  [ -n "$f" ] || continue
  echo "  ротация: удаляю старый $(basename "$f")"
  rm -f "$f"
done

TOTAL="$(ls -1 "$BACKUP_DIR"/dedecolog_*.dump 2>/dev/null | wc -l | tr -d ' ')"
echo "Бэкапов в $BACKUP_DIR: $TOTAL (храним последние $KEEP)"
