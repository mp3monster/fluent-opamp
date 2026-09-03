#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLI_ENTRY="${REPO_ROOT}/cli/main.py"
VENV_DIR="${REPO_ROOT}/.venv"

if [[ ! -f "${CLI_ENTRY}" ]]; then
  echo "Could not find CLI entrypoint: ${CLI_ENTRY}" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Could not find python3 or python on PATH." >&2
  exit 1
fi

cd "${REPO_ROOT}"
"${PYTHON_BIN}" "${CLI_ENTRY}" setup-venv --venv "${VENV_DIR}" "$@"
