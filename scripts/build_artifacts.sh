#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_ROOT="${REPO_ROOT}/dist"
PROVIDER_DIST="${DIST_ROOT}/provider"
CONSUMER_DIST="${DIST_ROOT}/consumer"
CATALOG_DIST="${DIST_ROOT}/catalog"
CLI_DIST="${DIST_ROOT}/cli"
CONSUMER_SIM_DIST="${DIST_ROOT}/consumer-sim"

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
for dist_dir in \
  "${PROVIDER_DIST}" \
  "${CONSUMER_DIST}" \
  "${CATALOG_DIST}" \
  "${CLI_DIST}" \
  "${CONSUMER_SIM_DIST}"
do
  mkdir -p "${dist_dir}"
  rm -f "${dist_dir}"/*
done

echo "Building provider artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${PROVIDER_DIST}" "${REPO_ROOT}/provider"

echo "Building consumer artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${CONSUMER_DIST}" "${REPO_ROOT}/consumer"

echo "Building catalog artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${CATALOG_DIST}" "${REPO_ROOT}/catalog-service"

echo "Building CLI artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${CLI_DIST}" "${REPO_ROOT}/cli"

echo "Building consumer-sim artifacts..."
"${PYTHON_BIN}" -m build --sdist --wheel --outdir "${CONSUMER_SIM_DIST}" "${REPO_ROOT}/consumer-sim"

echo "Build complete."
echo "Provider artifacts:"
ls -1 "${PROVIDER_DIST}"
echo "Consumer artifacts:"
ls -1 "${CONSUMER_DIST}"
echo "Catalog artifacts:"
ls -1 "${CATALOG_DIST}"
echo "CLI artifacts:"
ls -1 "${CLI_DIST}"
echo "Consumer-sim artifacts:"
ls -1 "${CONSUMER_SIM_DIST}"
