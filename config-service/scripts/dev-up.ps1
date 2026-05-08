Param()

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $RootDir ".run"
$LogDir = Join-Path $RunDir "logs"
$BackPidFile = Join-Path $RunDir "backend.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Resolve-Port {
    $env:PYTHONPATH = "$RootDir\src;$RootDir\..\provider\src"
    py -3 -c "from config_service.runtime_config import resolve_web_port; print(resolve_web_port())"
}

function Start-Backend {
    if (-not $env:APP_ENABLE_DEV_FEATURES) {
        $env:APP_ENABLE_DEV_FEATURES = "1"
    }
    if (-not $env:CONFIG_TOOL_LOG_LEVEL) {
        $env:CONFIG_TOOL_LOG_LEVEL = "DEBUG"
    }

    if (Test-Path $BackPidFile) {
        Remove-Item -Force $BackPidFile
    }
    if (Test-Path (Join-Path $RunDir "frontend.pid")) {
        Remove-Item -Force (Join-Path $RunDir "frontend.pid")
    }
    $port = (Resolve-Port | Out-String).Trim()

    Write-Host ""
    Write-Host "Config-service dev stack is starting in the current terminal."
    Write-Host "Backend:  http://localhost:$port/config-service/api/v1/health"
    Write-Host "UI:       http://localhost:$port/config-service/ui"
    Write-Host "Log level: $env:CONFIG_TOOL_LOG_LEVEL"
    Write-Host "Logs: $LogDir"
    Write-Host "Stop: press Ctrl+C"
    Write-Host ""

    $env:PYTHONPATH = "$RootDir\src;$RootDir\..\provider\src"
    cmd.exe /d /c "py -3 -m config_service 2>&1" |
        Tee-Object -FilePath (Join-Path $LogDir "backend.log") -Append
}

Start-Backend
