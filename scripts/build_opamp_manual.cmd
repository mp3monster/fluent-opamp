@echo off
setlocal EnableExtensions

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..

if exist "%REPO_ROOT%\.venv\Scripts\activate.bat" call "%REPO_ROOT%\.venv\Scripts\activate.bat"

python -m pip show reportlab >nul 2>&1
if errorlevel 1 (
  echo Installing Python package reportlab...
  python -m pip install reportlab
  if errorlevel 1 exit /b %ERRORLEVEL%
)

python "%SCRIPT_DIR%build_opamp_manual.py" --repo-root "%REPO_ROOT%" %*
exit /b %ERRORLEVEL%
