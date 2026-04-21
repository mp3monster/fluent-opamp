@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "BROKER_STOP_SCRIPT=%REPO_ROOT%\agent_broker\scripts\stop_broker_service.cmd"

if not exist "%BROKER_STOP_SCRIPT%" (
  echo Broker stop script not found: %BROKER_STOP_SCRIPT%
  exit /b 1
)

call "%BROKER_STOP_SCRIPT%" %*
exit /b %ERRORLEVEL%
