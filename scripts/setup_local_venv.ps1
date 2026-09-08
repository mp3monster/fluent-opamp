$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$CliEntry = Join-Path $RepoRoot "cli\main.py"
$VenvDir = Join-Path $RepoRoot ".venv"

if (-not (Test-Path $CliEntry)) {
    throw "Could not find CLI entrypoint: $CliEntry"
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $PythonCommand) {
    throw "Could not find python or py on PATH."
}

Push-Location $RepoRoot
try {
    & $PythonCommand.Source $CliEntry setup-venv --venv $VenvDir @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
