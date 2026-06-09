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

Write-Host "Checking whether the standalone CLI is available..."
$WarningScript = @"
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from shared.packaging_warnings import warn_if_cli_missing
except ModuleNotFoundError:
    raise SystemExit(0)

warn_if_cli_missing(
    component_label="broker zip build",
    repo_root=repo_root,
)
"@
python -c $WarningScript $RepoRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Compress-Archive -Path $PackageDir -DestinationPath $ZipPath -Force
