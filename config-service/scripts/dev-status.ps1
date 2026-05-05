Param()

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $RootDir ".run"
$BackPidFile = Join-Path $RunDir "backend.pid"

function Resolve-Port {
    $env:PYTHONPATH = "$RootDir;$RootDir\..\provider\src"
    py -3 -c "from config_service.runtime_config import resolve_web_port; print(resolve_web_port())"
}

if (Test-Path $BackPidFile) {
    Remove-Item -Force $BackPidFile
}
if (Test-Path (Join-Path $RunDir "frontend.pid")) {
    Remove-Item -Force (Join-Path $RunDir "frontend.pid")
}
Write-Host "Foreground mode: status is tied to the active terminal session running dev-up.ps1."
$port = (Resolve-Port | Out-String).Trim()
Write-Host "Check service availability at http://localhost:$port/config-service/api/v1/health"
