$ErrorActionPreference = "Stop"

if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
    throw "pg_restore is required to restore a PostgreSQL backup."
}

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL must be set."
}

if ($args.Count -lt 1) {
    throw "Usage: .\scripts\restore_postgres.ps1 <backup-file>"
}

$backupPath = $args[0]
if (-not (Test-Path $backupPath)) {
    throw "Backup file not found at $backupPath"
}

pg_restore --clean --if-exists --no-owner --no-privileges --dbname $env:DATABASE_URL $backupPath

Write-Host "Restore completed from $backupPath"
