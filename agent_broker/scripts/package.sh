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

echo "Checking whether the CLI is available..."
"${PYTHON_BIN}" "${ROOT_DIR}/../scripts/warn_if_cli_missing.py" \
  --repo-root "${ROOT_DIR}/.." \
  --component-label "broker deployment package"

zip -r "${OUT}/opamp-conversation-broker.zip" opamp_broker
