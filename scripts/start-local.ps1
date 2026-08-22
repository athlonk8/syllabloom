param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$Reload,
    [switch]$SkipInstall
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $projectRoot "scripts/run_local.py"
$launcherArgs = @($launcher, "--port", $Port)
if ($NoBrowser) { $launcherArgs += "--no-browser" }
if ($Reload) { $launcherArgs += "--reload" }
if ($SkipInstall) { $launcherArgs += "--skip-install" }

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & $py.Source -3 @launcherArgs
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python 3.11 or newer is required. Install Python, then run this script again."
    }
    & $python.Source @launcherArgs
}
exit $LASTEXITCODE
