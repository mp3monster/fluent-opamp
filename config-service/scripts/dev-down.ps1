Param()

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $RootDir ".run"
$BackPidFile = Join-Path $RunDir "backend.pid"

if (Test-Path $BackPidFile) {
    Remove-Item -Force $BackPidFile
}
if (Test-Path (Join-Path $RunDir "frontend.pid")) {
    Remove-Item -Force (Join-Path $RunDir "frontend.pid")
}
Write-Host "Foreground mode: stop the running server with Ctrl+C in the terminal where dev-up.ps1 is active."
