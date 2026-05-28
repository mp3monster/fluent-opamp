@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "CLI_ROOT=%%~fI"
set "CLI_ENTRY=%CLI_ROOT%\main.py"
set "MACRO_DIR=%USERPROFILE%\.opamp"
set "MACRO_FILE=%MACRO_DIR%\opamp-cli.doskey"

if not exist "%CLI_ENTRY%" (
  echo Could not find CLI entrypoint: %CLI_ENTRY%
  exit /b 1
)

if not exist "%MACRO_DIR%" mkdir "%MACRO_DIR%"

> "%MACRO_FILE%" echo opamp-cli=python "%CLI_ENTRY%" $*
>> "%MACRO_FILE%" echo opamp=python "%CLI_ENTRY%" $*

echo Wrote doskey macro file:
echo   %MACRO_FILE%
echo.
echo Load now in current cmd session:
echo   doskey /macrofile="%MACRO_FILE%"
echo.
echo Optional persistent setup for future cmd sessions:
echo   reg add "HKCU\Software\Command Processor" /v AutoRun /t REG_EXPAND_SZ /d "doskey /macrofile=\"%MACRO_FILE%\"" /f

exit /b 0
