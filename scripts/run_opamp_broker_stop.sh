#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BROKER_STOP_SCRIPT="${REPO_ROOT}/agent_broker/scripts/stop_broker_service.sh"

if [[ ! -f "${BROKER_STOP_SCRIPT}" ]]; then
  echo "Broker stop script not found: ${BROKER_STOP_SCRIPT}"
  exit 1
fi

"${BROKER_STOP_SCRIPT}" "$@"
