#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
BACK_PID_FILE="${RUN_DIR}/backend.pid"

rm -f "${BACK_PID_FILE}" "${RUN_DIR}/frontend.pid"
echo "Foreground mode: stop the running server with Ctrl+C in the terminal where dev-up.sh is active."
