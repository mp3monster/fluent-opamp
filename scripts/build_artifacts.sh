#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_ROOT="${REPO_ROOT}/dist"
PROVIDER_DIST="${DIST_ROOT}/provider"
CONSUMER_DIST="${DIST_ROOT}/consumer"

if [ -f "${REPO_ROOT}/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.venv/bin/activate"
fi

PYTHON_BIN="python3"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python runtime not found (expected python3 or python)." >&2
  exit 1
fi

echo "Refreshing component version metadata from git HEAD..."
"${PYTHON_BIN}" "${REPO_ROOT}/scripts/update_component_versions.py"

echo "Ensuring Python build tooling is available..."
"${PYTHON_BIN}" -m pip show build >/dev/null 2>&1 || "${PYTHON_BIN}" -m pip install build
echo "Ensuring PDF manual tooling is available..."
"${PYTHON_BIN}" -m pip show reportlab >/dev/null 2>&1 || "${PYTHON_BIN}" -m pip install reportlab

echo "Running security checks..."
"${PYTHON_BIN}" "${REPO_ROOT}/scripts/security_checks.py" --repo-root "${REPO_ROOT}" --python "${PYTHON_BIN}"

echo "Refreshing consolidated PDF manual..."
"${PYTHON_BIN}" "${REPO_ROOT}/scripts/build_opamp_manual.py" --repo-root "${REPO_ROOT}"

echo "Preparing artifact directories..."
mkdir -p "${PROVIDER_DIST}" "${CONSUMER_DIST}"
rm -f "${PROVIDER_DIST}"/* "${CONSUMER_DIST}"/*

echo "Building provider artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${PROVIDER_DIST}" "${REPO_ROOT}/provider"

echo "Building consumer artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${CONSUMER_DIST}" "${REPO_ROOT}/consumer"

echo "Build complete."
echo "Provider artifacts:"
ls -1 "${PROVIDER_DIST}"
echo "Consumer artifacts:"
ls -1 "${CONSUMER_DIST}"
