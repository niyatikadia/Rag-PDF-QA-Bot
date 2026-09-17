<#
    start-production.ps1 - start the backend in production mode.

    Deployment preparation exists so that the deploy itself is boring. The three
    ways this deploy can go quietly wrong are: starting without APP_ENV so the
    interactive API docs stay mounted, starting without a built frontend so the
    backend silently serves only the API, and starting without Ollama so every
    question returns 503. This script checks all three before binding a port,
    and refuses rather than starting something half-working.

    Usage:
        powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1
        ... -Port 9000          bind a different port
        ... -SkipOllamaCheck    start anyway with Ollama down

    Run from anywhere; paths are resolved relative to this file.
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$SkipOllamaCheck
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$DistDir    = Join-Path $RepoRoot "frontend\dist"
$Python     = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Fail($message, $fix) {
    Write-Host "  FAILED  $message" -ForegroundColor Red
    Write-Host "          $fix" -ForegroundColor Yellow
    exit 1
}

function Ok($message) { Write-Host "  ok      $message" -ForegroundColor Green }

Write-Host "`nPre-flight checks" -ForegroundColor Cyan

# 1. The virtual environment.
if (-not (Test-Path $Python)) {
    Fail "No virtual environment at backend\.venv" `
         "cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}
Ok "virtual environment"

# 2. Configuration.
if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
    Fail "backend\.env does not exist" `
         "copy backend\.env.example backend\.env"
}
Ok "backend\.env present"

# 3. The built frontend. Without this the backend still starts and still serves
#    the API, which is the failure worth catching: it looks fine until someone
#    opens the page and gets nothing.
if (-not (Test-Path (Join-Path $DistDir "index.html"))) {
    Fail "No frontend build at frontend\dist" `
         "cd frontend; npm ci; npm run build"
}
Ok "frontend bundle present"

# 4. Ollama. A stopped dependency is correctly reported as 503 by the service,
#    so this is a warning rather than a hard stop - but it is the single most
#    common reason a fresh deploy appears broken.
if (-not $SkipOllamaCheck) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" `
                          -UseBasicParsing -TimeoutSec 5 | Out-Null
        Ok "Ollama reachable"
    } catch {
        Write-Host "  WARNING Ollama is not reachable on 127.0.0.1:11434" -ForegroundColor Yellow
        Write-Host "          Start it with: ollama serve" -ForegroundColor Yellow
        Write-Host "          Questions will return 503 until it is running." -ForegroundColor Yellow
        Write-Host "          Pass -SkipOllamaCheck to silence this." -ForegroundColor Yellow
    }
}

# Production mode. Set here rather than relied upon from .env so that the
# process cannot start in development mode by inheriting a stale value.
$env:APP_ENV = "production"

Write-Host "`nStarting" -ForegroundColor Cyan
Write-Host "  APP_ENV     production (API docs not mounted)"
Write-Host "  Frontend    served from frontend\dist"
Write-Host "  Address     http://${BindHost}:${Port}"
Write-Host "  Bound to    $BindHost - loopback only; no authentication exists," -ForegroundColor Yellow
Write-Host "              so do not change this to 0.0.0.0." -ForegroundColor Yellow
Write-Host ""

Push-Location $BackendDir
try {
    & $Python -m uvicorn app.main:app --host $BindHost --port $Port
} finally {
    Pop-Location
}
