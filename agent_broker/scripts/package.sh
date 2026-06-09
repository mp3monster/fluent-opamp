#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT_DIR}/dist"
mkdir -p "${OUT}"
cd "${ROOT_DIR}/.."

PYTHON_BIN="python3"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python runtime not found (expected python3 or python)." >&2
  exit 1
fi

echo "Refreshing component version metadata from git HEAD..."
"${PYTHON_BIN}" "${ROOT_DIR}/../scripts/update_component_versions.py" --repo-root "${ROOT_DIR}/.."

echo "Checking whether the standalone CLI is available..."
"${PYTHON_BIN}" - "${ROOT_DIR}/.." <<'PY'
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
PY

ZIP_PATH="${OUT}/opamp-conversation-broker.zip"
if command -v zip >/dev/null 2>&1; then
  zip -r "${ZIP_PATH}" opamp_broker
else
  echo "zip command not found; using Python zipfile fallback..."
  "${PYTHON_BIN}" - "${ROOT_DIR}" "${ZIP_PATH}" <<'PY'
from pathlib import Path
import sys
import zipfile

root_dir = Path(sys.argv[1]).resolve()
zip_path = Path(sys.argv[2]).resolve()
package_dir = root_dir / "opamp_broker"

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in package_dir.rglob("*"):
        if path.is_file():
            archive.write(path, arcname=str(path.relative_to(root_dir)))
PY
fi
