@echo off
setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..

title OpAMP Consumer Sim Start

if exist "%REPO_ROOT%\.venv\Scripts\activate.bat" call "%REPO_ROOT%\.venv\Scripts\activate.bat"

set "APP_ENABLE_DEV_FEATURES=true"

python "%REPO_ROOT%\consumer-sim\src\consumer_sim_launcher.py" start %*
