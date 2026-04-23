#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
LINUX_VENV_DIR="${ROOT_DIR}/.venv-linux"
SERVICE_MODE=0
PYTHON_CMD=""
BROKER_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE_MODE=1
      shift
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        BROKER_ARGS+=("$1")
        shift
      done
      ;;
    *)
      BROKER_ARGS+=("$1")
      shift
      ;;
  esac
done

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export BROKER_CONFIG_PATH="${BROKER_CONFIG_PATH:-${ROOT_DIR}/opamp_broker/config/broker.ui_responses.json}"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

if [[ -x "${VENV_DIR}/bin/python" ]]; then
  PYTHON_CMD="${VENV_DIR}/bin/python"
else
  # A Windows-created .venv may not be usable from WSL/Linux shells.
  if [[ ! -x "${LINUX_VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${LINUX_VENV_DIR}"
  fi
  if [[ -x "${LINUX_VENV_DIR}/bin/python" ]]; then
    PYTHON_CMD="${LINUX_VENV_DIR}/bin/python"
  else
    echo "Unable to locate a runnable broker virtualenv Python."
    echo "Checked: ${VENV_DIR}/bin/python and ${LINUX_VENV_DIR}/bin/python"
    exit 1
  fi
fi

"${PYTHON_CMD}" -m pip install -r "${ROOT_DIR}/requirements.txt"

if [[ "${SERVICE_MODE}" -eq 0 ]]; then
  exec "${PYTHON_CMD}" -m opamp_broker.broker_app "${BROKER_ARGS[@]}"
fi

RUNTIME_DIR="${BROKER_RUNTIME_DIR:-${ROOT_DIR}/.broker}"
PID_FILE="${BROKER_PID_FILE:-${RUNTIME_DIR}/broker.pid}"
LOG_FILE="${BROKER_LOG_FILE:-${RUNTIME_DIR}/broker.log}"

mkdir -p "${RUNTIME_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(cat "${PID_FILE}")"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    echo "Broker already running (pid=${existing_pid})."
    echo "Log file: ${LOG_FILE}"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

nohup "${PYTHON_CMD}" -m opamp_broker.broker_app "${BROKER_ARGS[@]}" >>"${LOG_FILE}" 2>&1 &
broker_pid=$!
echo "${broker_pid}" >"${PID_FILE}"

sleep 1
if kill -0 "${broker_pid}" 2>/dev/null; then
  echo "Broker started (pid=${broker_pid})."
  echo "PID file: ${PID_FILE}"
  echo "Log file: ${LOG_FILE}"
  exit 0
fi

rm -f "${PID_FILE}"
echo "Broker failed to start. Check log file: ${LOG_FILE}"
exit 1
