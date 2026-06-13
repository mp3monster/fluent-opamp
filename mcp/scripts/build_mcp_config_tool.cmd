@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "MCP_DIR=%%~fI"
if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"
set "PYTHONPATH=%MCP_DIR%\src;%PYTHONPATH%"

"%PYTHON_BIN%" -m opamp_mcp_config.build_tool %*
endlocal
