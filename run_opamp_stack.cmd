@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "SCRIPT_DIR=%REPO_ROOT%\scripts"
set "SERVER_SCRIPT=%SCRIPT_DIR%\run_opamp_server.cmd"
set "SUPERVISORS_SCRIPT=%SCRIPT_DIR%\run_all_supervisors.cmd"
set "BROKER_SCRIPT=%SCRIPT_DIR%\run_opamp_broker.cmd"
set "APP_ENABLE_DEV_FEATURES=true"

if not exist "%SERVER_SCRIPT%" (
  echo Required script not found: %SERVER_SCRIPT%
  exit /b 1
)

if not exist "%SUPERVISORS_SCRIPT%" (
  echo Required script not found: %SUPERVISORS_SCRIPT%
  exit /b 1
)

if not exist "%BROKER_SCRIPT%" (
  echo Required script not found: %BROKER_SCRIPT%
  exit /b 1
)

echo Launching OpAMP server...
start "OpAMP Server" cmd /k call "%SERVER_SCRIPT%"

echo Waiting 5 seconds before starting supervisors...
timeout /t 5 /nobreak >nul

echo Launching supervisors...
call "%SUPERVISORS_SCRIPT%"

echo Waiting 5 seconds before starting opamp broker...
timeout /t 5 /nobreak >nul

echo Launching OpAMP broker...
start "OpAMP Broker" cmd /k call "%BROKER_SCRIPT%"

echo Launch sequence complete.
endlocal
