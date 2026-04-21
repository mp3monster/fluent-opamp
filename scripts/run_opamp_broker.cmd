@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "BROKER_ROOT=%REPO_ROOT%\agent_broker"
set "BROKER_SCRIPT=%REPO_ROOT%\agent_broker\scripts\start_broker.cmd"

title OpAMP Broker

if not exist "%BROKER_SCRIPT%" (
  echo Broker start script not found: %BROKER_SCRIPT%
  exit /b 1
)

if not exist "%BROKER_ROOT%" (
  echo Broker root directory not found: %BROKER_ROOT%
  exit /b 1
)

pushd "%BROKER_ROOT%" >nul
call "%BROKER_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
