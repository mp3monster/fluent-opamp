#!/usr/bin/env bash
set -euo pipefail

OPAMP_ROLE="${OPAMP_ROLE:-all}"
OPAMP_HOME="${OPAMP_HOME:-/opt/opamp}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root or with sudo." >&2
  exit 1
fi

stop_role() {
  local role="$1"
  case "$role" in
    server)
      systemctl stop opamp-provider config-service catalog-service svr-credentials-manager-service opamp-broker || true
      ;;
    consumer)
      systemctl stop opamp-consumer-simulator || true
      ;;
  esac
}

start_role() {
  local role="$1"
  case "$role" in
    server)
      bash "$SCRIPT_DIR/start-opamp-server.sh"
      ;;
    consumer)
      bash "$SCRIPT_DIR/start-opamp-consumer.sh"
      ;;
  esac
}

case "$OPAMP_ROLE" in
  server|consumer)
    stop_role "$OPAMP_ROLE"
    OPAMP_ROLE="$OPAMP_ROLE" bash "$SCRIPT_DIR/install-opamp.sh"
    start_role "$OPAMP_ROLE"
    ;;
  all)
    for role in server consumer; do
      stop_role "$role"
      OPAMP_ROLE="$role" bash "$SCRIPT_DIR/install-opamp.sh"
      start_role "$role"
    done
    ;;
  *)
    echo "Unsupported OPAMP_ROLE=$OPAMP_ROLE. Use server, consumer, or all." >&2
    exit 1
    ;;
esac

echo "Upgrade completed for OPAMP_ROLE=$OPAMP_ROLE"
