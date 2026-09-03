#!/usr/bin/env bash
set -euo pipefail

OPAMP_REPO="${OPAMP_REPO:-/workspace/opamp}"
REPORT_DIR="${REPORT_DIR:-${OPAMP_REPO}/dist/test-reports/consumer-plugin-startup}"

python3 /opt/opamp-regression/run_consumer_plugin_startup.py \
  --repo-root "${OPAMP_REPO}" \
  --report-dir "${REPORT_DIR}" \
  --install \
  "$@"
