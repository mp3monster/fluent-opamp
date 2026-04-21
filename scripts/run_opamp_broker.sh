#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BROKER_SCRIPT="${REPO_ROOT}/agent_broker/scripts/start_broker.sh"
BROKER_ROOT="${REPO_ROOT}/agent_broker"

if [[ -t 1 ]]; then
  printf '\033]0;%s\007' "OpAMP Broker"
fi

if [[ ! -f "${BROKER_SCRIPT}" ]]; then
  echo "Broker start script not found: ${BROKER_SCRIPT}"
  exit 1
fi

if [[ ! -d "${BROKER_ROOT}" ]]; then
  echo "Broker root directory not found: ${BROKER_ROOT}"
  exit 1
fi

(
  cd "${BROKER_ROOT}"
  "${BROKER_SCRIPT}" "$@"
)
