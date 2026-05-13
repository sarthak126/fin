# Production Rehearsal Workflow

This repo now includes a concrete production-like rehearsal path that exercises:

- PostgreSQL migrations on container boot
- strict backend startup in `APP_ENV=production`
- S3 object storage through LocalStack
- KMS-backed server-side encryption using a rehearsal alias
- rollback mechanics via explicit Postgres backup and restore scripts

## Rehearsal stack

Use [`docker-compose.rehearsal.yml`](../docker-compose.rehearsal.yml) to boot:

- `postgres`
- `localstack` with `s3` and `kms`
- `rehearsal-init` to create the bucket + KMS alias
- `backend` in strict production mode
- `frontend`
- `rehearsal-smoke` to verify health + encrypted object storage

Run:

```bash
docker compose -f docker-compose.rehearsal.yml up --build --abort-on-container-exit rehearsal-smoke
```

If you want the full stack to remain up for manual inspection:

```bash
docker compose -f docker-compose.rehearsal.yml up --build
```

## What gets verified

`backend/scripts/rehearse_production.py` waits for:

- `GET /health/live`
- `GET /health/ready`

It then uploads a sample PDF through the same storage service the app uses, downloads it back, stores a password blob, and checks that both remote objects were written with:

- `aws:kms` when `AWS_KMS_KEY_ID` is configured
- `AES256` when a KMS key is not configured

## Backup and rollback drill

Take a Postgres backup before any rehearsal or production migration:

```bash
cd backend
DATABASE_URL=postgresql://... ./scripts/backup_postgres.sh
```

On Windows PowerShell:

```powershell
cd backend
$env:DATABASE_URL = "postgresql://..."
.\scripts\backup_postgres.ps1
```

To restore:

```bash
cd backend
DATABASE_URL=postgresql://... ./scripts/restore_postgres.sh ./backups/loanlens-<timestamp>.dump
```

On Windows PowerShell:

```powershell
cd backend
$env:DATABASE_URL = "postgresql://..."
.\scripts\restore_postgres.ps1 .\backups\loanlens-<timestamp>.dump
```

## Rollout expectations

- `backend` must come up healthy without degraded fallback.
- `rehearsal-init` must complete successfully before the backend starts.
- `rehearsal-smoke` must exit `0`.
- If migrations fail, restore the latest backup and redeploy the previous image.

## Required env for remote object storage

Add these to real production or rehearsal environments:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `S3_BUCKET_NAME`
- `AWS_S3_ENDPOINT_URL` for LocalStack or non-AWS endpoints
- `AWS_KMS_ENDPOINT_URL` when KMS is not reachable through the default AWS endpoint
- `AWS_KMS_KEY_ID` for explicit KMS-backed encryption
- `AWS_S3_FORCE_PATH_STYLE=true` for LocalStack / path-style S3 endpoints
