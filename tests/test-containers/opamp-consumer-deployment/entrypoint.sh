#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${TEST_CONTAINER_CONFIG:-/config/test-container.env}"
export TEST_CONTAINER_CONFIG="${CONFIG_PATH}"

if [[ ! -f "${TEST_CONTAINER_CONFIG}" ]]; then
  echo "[entrypoint] config file not found: ${TEST_CONTAINER_CONFIG}" >&2
  exit 2
fi

python3 /opt/opamp-test/bootstrap.py
