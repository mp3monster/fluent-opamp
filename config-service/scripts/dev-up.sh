#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
LOG_DIR="${RUN_DIR}/logs"
BACK_PID_FILE="${RUN_DIR}/backend.pid"

mkdir -p "${LOG_DIR}"

resolve_port() {
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/../provider/src" python3 -c \
    "from config_service.runtime_config import resolve_web_port; print(resolve_web_port())"
}

is_truthy() {
  local raw="${1:-}"
  local normalized
  normalized="$(printf '%s' "${raw}" | tr '[:upper:]' '[:lower:]' | xargs)"
  [[ "${normalized}" == "1" || "${normalized}" == "true" || "${normalized}" == "yes" || "${normalized}" == "on" ]]
}

start_backend() {
  export APP_ENABLE_DEV_FEATURES="${APP_ENABLE_DEV_FEATURES:-1}"
  rm -f "${BACK_PID_FILE}"
  rm -f "${RUN_DIR}/frontend.pid"
  local port
  port="$(resolve_port)"

  echo
  echo "Config-service dev stack is starting in the current terminal."
  echo "Backend:  http://localhost:${port}/config-service/api/v1/health"
  echo "UI:       http://localhost:${port}/config-service/ui"
  echo "Logs: ${LOG_DIR}"
  echo "Stop: press Ctrl+C"
  echo

  cd "${ROOT_DIR}"
  if is_truthy "${APP_ENABLE_DEV_FEATURES}"; then
    echo "Dev mode log mirror enabled: backend logs are written to ${LOG_DIR}/backend.log and console."
    PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/../provider/src" python3 "${ROOT_DIR}/config_service/app.py" 2>&1 | tee -a "${LOG_DIR}/backend.log"
  else
    PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/../provider/src" python3 "${ROOT_DIR}/config_service/app.py" 2>&1 | tee -a "${LOG_DIR}/backend.log"
  fi
}

start_backend
