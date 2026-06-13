@echo off
setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..
set DIST_ROOT=%REPO_ROOT%\dist
set PROVIDER_DIST=%DIST_ROOT%\provider
set CONSUMER_DIST=%DIST_ROOT%\consumer
set CATALOG_DIST=%DIST_ROOT%\catalog
set CLI_DIST=%DIST_ROOT%\cli
set CONSUMER_SIM_DIST=%DIST_ROOT%\consumer-sim

if exist "%REPO_ROOT%\.venv\Scripts\activate.bat" call "%REPO_ROOT%\.venv\Scripts\activate.bat"

echo Refreshing component version metadata from git HEAD...
python "%REPO_ROOT%\scripts\update_component_versions.py"
if errorlevel 1 exit /b 1

echo Ensuring Python build tooling is available...
python -m pip show build >nul 2>&1 || python -m pip install build
echo Ensuring PDF manual tooling is available...
python -m pip show reportlab >nul 2>&1 || python -m pip install reportlab

echo Running security checks...
python "%REPO_ROOT%\scripts\security_checks.py" --repo-root "%REPO_ROOT%" --python python
if errorlevel 1 exit /b 1

echo Refreshing consolidated PDF manual...
python "%REPO_ROOT%\scripts\build_opamp_manual.py" --repo-root "%REPO_ROOT%"
if errorlevel 1 exit /b 1

echo Preparing artifact directories...
if not exist "%PROVIDER_DIST%" mkdir "%PROVIDER_DIST%"
if not exist "%CONSUMER_DIST%" mkdir "%CONSUMER_DIST%"
if not exist "%CATALOG_DIST%" mkdir "%CATALOG_DIST%"
if not exist "%CLI_DIST%" mkdir "%CLI_DIST%"
if not exist "%CONSUMER_SIM_DIST%" mkdir "%CONSUMER_SIM_DIST%"
del /q "%PROVIDER_DIST%\*" >nul 2>&1
del /q "%CONSUMER_DIST%\*" >nul 2>&1
del /q "%CATALOG_DIST%\*" >nul 2>&1
del /q "%CLI_DIST%\*" >nul 2>&1
del /q "%CONSUMER_SIM_DIST%\*" >nul 2>&1

echo Building provider artifacts...
python -m build --sdist --wheel --outdir "%PROVIDER_DIST%" "%REPO_ROOT%\provider"
if errorlevel 1 exit /b 1

echo Building consumer artifacts...
python -m build --sdist --wheel --outdir "%CONSUMER_DIST%" "%REPO_ROOT%\consumer"
if errorlevel 1 exit /b 1

echo Building catalog artifacts...
python -m build --sdist --wheel --outdir "%CATALOG_DIST%" "%REPO_ROOT%\catalog-service"
if errorlevel 1 exit /b 1

echo Building CLI artifacts...
python -m build --sdist --wheel --outdir "%CLI_DIST%" "%REPO_ROOT%\cli"
if errorlevel 1 exit /b 1

echo Building consumer-sim artifacts...
python -m build --sdist --wheel --outdir "%CONSUMER_SIM_DIST%" "%REPO_ROOT%\consumer-sim"
if errorlevel 1 exit /b 1

echo Build complete.
echo Provider artifacts:
dir /b "%PROVIDER_DIST%"
echo Consumer artifacts:
dir /b "%CONSUMER_DIST%"
echo Catalog artifacts:
dir /b "%CATALOG_DIST%"
echo CLI artifacts:
dir /b "%CLI_DIST%"
echo Consumer-sim artifacts:
dir /b "%CONSUMER_SIM_DIST%"
