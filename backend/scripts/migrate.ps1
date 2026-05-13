$ErrorActionPreference = "Stop"

$venvScripts = Join-Path (Get-Location) "venv\Scripts"
if (Test-Path $venvScripts) {
    $env:PATH = "$venvScripts;$env:PATH"
}

function Import-DotEnvFile {
    param(
        [string]$Path = ".env"
    )

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }

        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        if (-not $name -or (Test-Path "Env:$name")) {
            continue
        }

        $value = $parts[1].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        Set-Item -Path "Env:$name" -Value $value
    }
}

if (-not $env:DATABASE_URL) {
    Import-DotEnvFile
}

function Resolve-SchemaPath {
    if ($env:PRISMA_SCHEMA_PATH) {
        return $env:PRISMA_SCHEMA_PATH
    }

    return ".\schema.prisma"
}

$prismaBin = ".\venv\Scripts\prisma.exe"
$appEnv = if ($env:APP_ENV) { $env:APP_ENV } else { "development" }

function Invoke-PrismaCommand {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $prismaBin @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Prisma command failed: $prismaBin $($Arguments -join ' ')"
    }
}

function Invoke-PrismaCommandWithOutput {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $previousNativePreference = $null

    try {
        $script:ErrorActionPreference = "Continue"

        if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
            $previousNativePreference = $PSNativeCommandUseErrorActionPreference
            $script:PSNativeCommandUseErrorActionPreference = $false
        }

        $output = & $prismaBin @Arguments 2>&1 | ForEach-Object { $_.ToString() }
        $exitCode = $LASTEXITCODE
    } finally {
        $script:ErrorActionPreference = $previousErrorActionPreference

        if ($null -ne $previousNativePreference) {
            $script:PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
    }

    $outputText = $output -join [Environment]::NewLine

    if ($outputText) {
        Write-Host $outputText
    }

    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output   = $outputText
    }
}

$schemaPath = Resolve-SchemaPath
$migrationsDir = Join-Path (Split-Path $schemaPath -Parent) "migrations"

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL must be set to a PostgreSQL connection string."
}

if (-not ($env:DATABASE_URL.StartsWith("postgresql://") -or $env:DATABASE_URL.StartsWith("postgres://"))) {
    throw "SQLite DATABASE_URL values are no longer supported. Set DATABASE_URL to a PostgreSQL connection string."
}

if (-not $env:DIRECT_URL) {
    $env:DIRECT_URL = $env:DATABASE_URL
}

Write-Host "Starting DB migration flow..."
Write-Host "Using Prisma schema: $schemaPath"

if (-not (Test-Path $schemaPath)) {
    throw "Prisma schema not found at $schemaPath"
}

if (Test-Path $migrationsDir) {
    Write-Host "Running formal deploy of DB migrations from $migrationsDir..."
    $deployResult = Invoke-PrismaCommandWithOutput migrate deploy --schema $schemaPath

    if ($deployResult.ExitCode -ne 0) {
        throw "Prisma command failed: $prismaBin migrate deploy --schema $schemaPath"
    }
} else {
    if ($appEnv -eq "production") {
        throw "No migrations directory found for $schemaPath. Refusing to fall back to 'prisma db push' in production."
    }

    Write-Warning "No migrations directory found for $schemaPath. Falling back to 'prisma db push' for local prototyping only."
    Invoke-PrismaCommand db push --schema $schemaPath
}

Write-Host "Generating Prisma client..."
Invoke-PrismaCommand generate --schema $schemaPath
Write-Host "Migration pipeline complete."
