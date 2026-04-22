@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

git -C "%REPO_ROOT%" config --local core.hooksPath .githooks
if errorlevel 1 (
  echo Failed to configure core.hooksPath.
  exit /b 1
)

for /f "usebackq delims=" %%I in (`git -C "%REPO_ROOT%" rev-parse --git-common-dir`) do set "GIT_COMMON_DIR=%%I"
if not defined GIT_COMMON_DIR (
  echo Failed to resolve git common directory.
  exit /b 1
)
set "FIRST_CHAR=%GIT_COMMON_DIR:~0,1%"
set "SECOND_CHAR=%GIT_COMMON_DIR:~1,1%"
if "%FIRST_CHAR%"=="\" (
  set "HOOKS_DIR=%GIT_COMMON_DIR%\hooks"
) else if "%SECOND_CHAR%"==":" (
  set "HOOKS_DIR=%GIT_COMMON_DIR%\hooks"
) else (
  set "HOOKS_DIR=%REPO_ROOT%\%GIT_COMMON_DIR%\hooks"
)
if not exist "%HOOKS_DIR%" mkdir "%HOOKS_DIR%"

set "LEGACY_PRE_COMMIT=%HOOKS_DIR%\pre-commit"
set "WRITE_SHIM=1"
if exist "%LEGACY_PRE_COMMIT%" (
  findstr /c:"opamp-hook-shim" "%LEGACY_PRE_COMMIT%" >nul 2>&1
  if errorlevel 1 (
    set "WRITE_SHIM=0"
    echo Detected existing custom %LEGACY_PRE_COMMIT%; leaving it unchanged.
  )
)

if "%WRITE_SHIM%"=="1" (
  > "%LEGACY_PRE_COMMIT%" echo #!/usr/bin/env bash
  >> "%LEGACY_PRE_COMMIT%" echo set -euo pipefail
  >> "%LEGACY_PRE_COMMIT%" echo # opamp-hook-shim: legacy .git/hooks fallback for GUI clients.
  >> "%LEGACY_PRE_COMMIT%" echo REPO_ROOT="$^(git rev-parse --show-toplevel^)"
  >> "%LEGACY_PRE_COMMIT%" echo exec "${REPO_ROOT}/.githooks/pre-commit" "$@"
)

echo Configured git hooks path to %REPO_ROOT%\.githooks
echo Verified fallback shim at %LEGACY_PRE_COMMIT%
exit /b 0
