#!/usr/bin/env sh
set -eu

if [ -d "./venv/bin" ]; then
    PATH="$(pwd)/venv/bin:$PATH"
elif [ -d "./venv/Scripts" ]; then
    PATH="$(pwd)/venv/Scripts:$PATH"
fi

if [ -z "${DATABASE_URL:-}" ] && [ -f "./.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "./.env"
    set +a
fi

resolve_schema_path() {
    if [ -n "${PRISMA_SCHEMA_PATH:-}" ]; then
        printf '%s' "$PRISMA_SCHEMA_PATH"
        return
    fi

    printf '%s' "./schema.prisma"
}

SCHEMA_PATH="$(resolve_schema_path)"
MIGRATIONS_DIR="$(dirname "$SCHEMA_PATH")/migrations"
APP_ENV_VALUE="${APP_ENV:-development}"

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL must be set to a PostgreSQL connection string."
    exit 1
fi

case "${DATABASE_URL:-}" in
    postgresql://*|postgres://*) ;;
    *)
        echo "ERROR: SQLite DATABASE_URL values are no longer supported."
        echo "Set DATABASE_URL to a PostgreSQL connection string."
        exit 1
        ;;
esac

if [ -z "${DIRECT_URL:-}" ]; then
    DIRECT_URL="$DATABASE_URL"
    export DIRECT_URL
fi

echo "Starting DB migration flow..."
echo "Using Prisma schema: $SCHEMA_PATH"

if [ ! -f "$SCHEMA_PATH" ]; then
    echo "ERROR: Prisma schema not found at $SCHEMA_PATH"
    exit 1
fi

if [ -d "$MIGRATIONS_DIR" ]; then
    echo "Running formal deploy of DB migrations from $MIGRATIONS_DIR..."
    if DEPLOY_OUTPUT="$(prisma migrate deploy --schema "$SCHEMA_PATH" 2>&1)"; then
        printf '%s\n' "$DEPLOY_OUTPUT"
    else
        DEPLOY_EXIT_CODE=$?
        printf '%s\n' "$DEPLOY_OUTPUT"
        exit "$DEPLOY_EXIT_CODE"
    fi
else
    if [ "$APP_ENV_VALUE" = "production" ]; then
        echo "ERROR: No migrations directory found for $SCHEMA_PATH."
        echo "Refusing to fall back to 'prisma db push' in production."
        exit 1
    fi

    echo "WARNING: No migrations directory found for $SCHEMA_PATH."
    echo "Falling back to 'prisma db push' for local prototyping only."
    prisma db push --schema "$SCHEMA_PATH"
fi

echo "Generating Prisma client..."
prisma generate --schema "$SCHEMA_PATH"

echo "Migration pipeline complete."
