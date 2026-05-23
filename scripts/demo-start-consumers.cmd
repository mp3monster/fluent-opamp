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

title OpAMP Demo Start Consumers

set "SIM_SCRIPT=%SCRIPT_DIR%run_consumer_sim_start.cmd"
set "FLB_SCRIPT=%SCRIPT_DIR%run_fluentbit_supervisor.cmd"
set "FLD_SCRIPT=%SCRIPT_DIR%run_fluentd_supervisor.cmd"

if not exist "%SIM_SCRIPT%" (
  echo Required script not found: %SIM_SCRIPT%
  exit /b 1
)
if not exist "%FLB_SCRIPT%" (
  echo Required script not found: %FLB_SCRIPT%
  exit /b 1
)
if not exist "%FLD_SCRIPT%" (
  echo Required script not found: %FLD_SCRIPT%
  exit /b 1
)

echo Launching run_consumer_sim_start.cmd
start "OpAMP Consumer Sim" /D "%REPO_ROOT%" "%SIM_SCRIPT%"

echo Launching run_fluentbit_supervisor.cmd
start "OpAMP FluentBit Consumer" /D "%REPO_ROOT%" "%FLB_SCRIPT%"

echo Launching run_fluentd_supervisor.cmd
start "OpAMP Fluentd Consumer" /D "%REPO_ROOT%" "%FLD_SCRIPT%"

echo Consumer demo launch requested for simulator + fluentbit + fluentd clients.

endlocal
