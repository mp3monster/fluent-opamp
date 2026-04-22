$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $RootDir "dist"
$ZipPath = Join-Path $OutDir "opamp-conversation-broker.zip"
$PackageDir = Join-Path $RootDir "opamp_broker"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

$RepoRoot = Split-Path -Parent $RootDir
$VersionScript = Join-Path $RepoRoot "scripts\update_component_versions.py"
Write-Host "Refreshing component version metadata from git HEAD..."
python $VersionScript --repo-root $RepoRoot

Compress-Archive -Path $PackageDir -DestinationPath $ZipPath -Force
