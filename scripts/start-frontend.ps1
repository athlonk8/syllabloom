$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $projectRoot 'frontend')
if (-not (Test-Path -LiteralPath 'node_modules')) {
    npm install
}
npm run dev
