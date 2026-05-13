$ErrorActionPreference = "Stop"

if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    throw "pg_dump is required to create a PostgreSQL backup."
}

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL must be set."
}

$backupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { ".\backups" }
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$backupPath = if ($args.Count -gt 0) { $args[0] } else { Join-Path $backupDir "loanlens-$timestamp.dump" }

New-Item -ItemType Directory -Force -Path (Split-Path $backupPath -Parent) | Out-Null
pg_dump --format=custom --no-owner --no-privileges --file $backupPath $env:DATABASE_URL

Write-Host "Backup written to $backupPath"
