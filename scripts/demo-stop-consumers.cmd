@echo off
REM Copyright 2026 mp3monster.org
REM Licensed under the Apache License, Version 2.0 (the "License");
REM you may not use this file except in compliance with the License.
REM You may obtain a copy of the License at
REM http://www.apache.org/licenses/LICENSE-2.0
REM
REM Unless required by applicable law or agreed to in writing, software
REM distributed under the License is distributed on an "AS IS" BASIS,
REM WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
REM See the License for the specific language governing permissions and
REM limitations under the License.

setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "SEMAPHORE_PATH=%REPO_ROOT%\OpAMPSupervisor.signal"

title OpAMP Demo Stop Consumers

echo Stopping consumer simulator launcher instances...
if exist "%SCRIPT_DIR%run_consumer_sim_stop.cmd" (
  pushd "%REPO_ROOT%" >nul
  call "%SCRIPT_DIR%run_consumer_sim_stop.cmd"
  popd >nul
)

echo Requesting graceful shutdown for fluentbit/fluentd consumer clients via semaphore...
type nul > "%SEMAPHORE_PATH%"

where timeout >nul 2>&1
if %errorlevel%==0 (
  timeout /t 2 /nobreak >nul
)

if exist "%SCRIPT_DIR%terminate_fluent_bit.cmd" (
  call "%SCRIPT_DIR%terminate_fluent_bit.cmd"
)

where powershell >nul 2>&1
if %errorlevel%==0 (
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'opamp_consumer\.fluentbit_client' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'opamp_consumer\.fluentd_client' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
) else (
  taskkill /F /IM python.exe /FI "WINDOWTITLE eq OpAMP Supervisor*" >nul 2>&1
)

echo Stop request complete.
echo Note: %SEMAPHORE_PATH% is intentionally left in place until next launch removes it.

endlocal
