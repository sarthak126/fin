#!/usr/bin/env sh
set -eu

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump is required to create a PostgreSQL backup."
    exit 1
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_PATH="${1:-$BACKUP_DIR/loanlens-$TIMESTAMP.dump}"

mkdir -p "$(dirname "$BACKUP_PATH")"
pg_dump --format=custom --no-owner --no-privileges --file "$BACKUP_PATH" "$DATABASE_URL"

echo "Backup written to $BACKUP_PATH"
