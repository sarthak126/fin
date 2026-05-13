# Database Migration Workflow

This repo now uses one canonical Prisma schema and migration history for PostgreSQL:

- schema: [`schema.prisma`](./schema.prisma)
- migrations: [`migrations/`](./migrations)

## Schema selection

The bootstrap scripts resolve the Prisma schema in this order:

1. `PRISMA_SCHEMA_PATH`
2. default -> `./schema.prisma`

## Local development

1. Copy `.env.example` to `.env`.
2. Point both database URLs at PostgreSQL:
   ```bash
   DATABASE_PROVIDER=postgresql
   DATABASE_URL=postgresql://loanlens:loanlens@localhost:5432/loanlens
   DIRECT_URL=postgresql://loanlens:loanlens@localhost:5432/loanlens
   PRISMA_SCHEMA_PATH=./schema.prisma
   ```
3. Run the bootstrap script:
   ```bash
   sh ./scripts/migrate.sh
   ```
   On Windows PowerShell:
   ```powershell
   .\scripts\migrate.ps1
   ```
   Both scripts automatically load `backend/.env` before running Prisma.

If `DIRECT_URL` is omitted, the bootstrap scripts reuse `DATABASE_URL`.

When you change the schema, create a migration from the canonical PostgreSQL schema:
```bash
prisma migrate dev --schema ./schema.prisma --name <descriptive_name>
prisma generate --schema ./schema.prisma
```

## Staging / production

Production uses the same checked-in schema and migration history:

```bash
export DATABASE_PROVIDER=postgresql
export DATABASE_URL=postgresql://postgres:password@db.example.com:5432/loanlens
export DIRECT_URL=postgresql://postgres:password@db.example.com:5432/loanlens
prisma migrate deploy --schema ./schema.prisma
prisma generate --schema ./schema.prisma
```

The container bootstrap path does this automatically before starting `uvicorn`.

## Safety rules

- SQLite connection strings are rejected during startup and migration bootstrap.
- `scripts/migrate.sh` refuses to fall back to `db push` when `APP_ENV=production`.
- Keep `DIRECT_URL` on a direct PostgreSQL connection when `DATABASE_URL` goes through a pooler.

## Legacy case backfill

Migration `20260419120000_case_domain` introduces the `cases` and `case_analyses`
tables and backfills pre-existing data into the new case aggregate.

Backfill rules:

- Every existing row in `documents` becomes a one-document legacy case.
- The legacy case reuses the source document UUID as `cases.id` so the mapping is deterministic.
- `cases.legacy_source_document_id` stores the original seed document explicitly for auditability.
- `documents.case_id` is populated for every legacy document.
- Existing `analyses` rows are mirrored into `case_analyses` using the same analysis UUIDs.
- Legacy case status is derived from document processing state:
  - `analyzed -> finalized`
  - `pending`, `processing`, `failed`, and any other non-final state -> `collecting`

This strategy preserves document-to-case traceability for historical data without
requiring a separate mapping table, while still leaving cases free to collect
additional documents after the migration.

Migration `20260419133000_case_applicant_info` then adds the explicit
`applicant_name`, `applicant_email`, and `applicant_phone` columns used by the
case CRUD endpoints.

Migration `20260420110000_case_analysis_is_final` adds the `case_analyses.is_final`
flag used to distinguish provisional case aggregates from future final case
decisions. Existing historical rows default to `false`.
