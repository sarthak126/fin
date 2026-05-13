#!/usr/bin/env sh
set -eu

if ! command -v pg_restore >/dev/null 2>&1; then
    echo "ERROR: pg_restore is required to restore a PostgreSQL backup."
    exit 1
fi

: "${DATABASE_URL:?DATABASE_URL must be set}"

BACKUP_PATH="${1:-}"
if [ -z "$BACKUP_PATH" ]; then
    echo "Usage: ./scripts/restore_postgres.sh <backup-file>"
    exit 1
fi

if [ ! -f "$BACKUP_PATH" ]; then
    echo "ERROR: Backup file not found at $BACKUP_PATH"
    exit 1
fi

pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$DATABASE_URL" "$BACKUP_PATH"

echo "Restore completed from $BACKUP_PATH"
