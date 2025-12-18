param(
  [string]$PgHost = "localhost",
  [int]$PgPort = 5432,
  [string]$PgSuperUser = "chatbot_user",
  [string]$DbName = "chatbot_dev",
  [string]$AppUserPassword = "REPLACE_ME_STRONG_PASSWORD", # pragma: allowlist secret
  [switch]$RunMigrations = $true
)

# Resolve repo root (this script lives in scripts/ps/) and common paths
$RepoRootPath = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$SqlDir = Join-Path $RepoRootPath "db\sql"
$ComposeMain = Join-Path $RepoRootPath "docker-compose.yml"
$ComposeTenancy = Join-Path $RepoRootPath "docker-compose.tenancy.yml"
$VerifySqlPath = Join-Path $SqlDir "verify_tenancy.sql"

function Test-Command {
  param([string]$Name)
  $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-PsqlFile {
  param(
    [string]$FilePath,
    [string]$Host,
    [int]$Port,
    [string]$User,
    [string]$Db
  )
  if (Test-Command -Name "psql") {
    & psql -h $Host -p $Port -U $User -d $Db -v ON_ERROR_STOP=1 -f $FilePath
  } else {
    Write-Host "psql not found on PATH; using dockerized postgres client..."
    $rel = ($FilePath.Substring($RepoRootPath.Length + 1) -replace "\\","/")
    docker run --rm `
      -e PGPASSWORD="$env:PGPASSWORD" `
      -v "${RepoRootPath}:/work" `
      -w /work `
      postgres:15-alpine `
      psql -h $Host -p $Port -U $User -d $Db -v ON_ERROR_STOP=1 -f ("/work/" + $rel)
  }
}

# 1) Create app_user and grants (requires superuser)
Write-Host "Creating role app_user (if not exists) and granting privileges..."
$env:PGPASSWORD = Read-Host -AsSecureString "Enter password for Postgres superuser ($PgSuperUser)" | `
  ForEach-Object { (New-Object System.Net.NetworkCredential("", $_)).Password }

$createSqlPath = Join-Path $SqlDir "create_app_user.sql"
$createSqlTemp = Join-Path $SqlDir "create_app_user.tmp.sql"
(Get-Content $createSqlPath) `
  -replace "REPLACE_ME_STRONG_PASSWORD", $AppUserPassword |
  Set-Content -NoNewline $createSqlTemp

Invoke-PsqlFile -FilePath $createSqlTemp -Host $PgHost -Port $PgPort -User $PgSuperUser -Db $DbName
Remove-Item $createSqlTemp -Force

# 2) Prepare DATABASE_URL for app_user
# Use URL-encoding for password to avoid parsing issues
$encodedPwd = [System.Uri]::EscapeDataString($AppUserPassword)
$dbUrl = "postgresql+psycopg2://app_user:${encodedPwd}@${PgHost}:${PgPort}/${DbName}"
Write-Host "DATABASE_URL for app_user:" $dbUrl

# 3) Optionally run Alembic migrations via Docker Compose
if ($RunMigrations) {
  Write-Host "Running Alembic migrations with docker-compose.tenancy.yml..."
  $env:DATABASE_URL_APPUSER = $dbUrl
  docker compose -f "$ComposeMain" -f "$ComposeTenancy" build db-migrate
  docker compose -f "$ComposeMain" -f "$ComposeTenancy" run --rm db-migrate
}

# 4) Verification queries
Write-Host "`nRun verification:"
Write-Host "  psql -h $PgHost -p $PgPort -U $PgSuperUser -d $DbName -f `"$VerifySqlPath`""


