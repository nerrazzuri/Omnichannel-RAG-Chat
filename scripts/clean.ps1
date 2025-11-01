Param(
    [switch]$NoUp
)

Write-Host "[clean] Stopping stack and removing volumes..." -ForegroundColor Cyan
docker compose down -v | Out-Null

Write-Host "[clean] Removing local storage folders (if any)..." -ForegroundColor Cyan
foreach ($p in @(".\storage\*", ".\frontend\storage\*", ".\backend\src\storage\*")) {
    try { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue } catch {}
}

# Also try removing any lingering Docker volumes that match our services
Write-Host "[clean] Removing lingering Docker volumes (postgres/qdrant/redis)..." -ForegroundColor Cyan
$vols = docker volume ls -q | Where-Object { $_ -match 'postgres|qdrant|redis|omni|chatbot' }
foreach ($v in $vols) { try { docker volume rm $v | Out-Null } catch {} }

if (-not $NoUp) {
    Write-Host "[clean] Starting stack..." -ForegroundColor Cyan
    docker compose up -d | Out-Null
    Write-Host "[clean] Done. Stack is up with a clean database." -ForegroundColor Green
} else {
    Write-Host "[clean] Done. Stack is stopped; start later with 'docker compose up -d'." -ForegroundColor Yellow
}


