#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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

echo "Ensuring PDF manual tooling is available..."
"${PYTHON_BIN}" -m pip show reportlab >/dev/null 2>&1 || "${PYTHON_BIN}" -m pip install reportlab

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/build_opamp_manual.py" --repo-root "${REPO_ROOT}" "$@"
