param([switch]$Reload)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create the .venv first: python -m venv .venv, then install backend requirements.'
}
Set-Location (Join-Path $projectRoot 'backend')
& (Join-Path $projectRoot '.venv\Scripts\alembic.exe') -c alembic.ini upgrade head
if ($Reload) {
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
} else {
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
