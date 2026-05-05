#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
BACK_PID_FILE="${RUN_DIR}/backend.pid"

resolve_port() {
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/../provider/src" python3 -c \
    "from config_service.runtime_config import resolve_web_port; print(resolve_web_port())"
}

rm -f "${BACK_PID_FILE}" "${RUN_DIR}/frontend.pid"
echo "Foreground mode: status is tied to the active terminal session running dev-up.sh."
echo "Check service availability at http://localhost:$(resolve_port)/config-service/api/v1/health"
