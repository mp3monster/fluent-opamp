$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot

$env:PYTHONUNBUFFERED = "1"
if (-not $env:BROKER_CONFIG_PATH) {
    $env:BROKER_CONFIG_PATH = Join-Path $RootDir "opamp_broker\config\broker.ui_responses.json"
}

Set-Location $RootDir
python -m opamp_broker.broker_app
