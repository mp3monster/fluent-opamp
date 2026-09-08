#!/usr/bin/env bash
set -euo pipefail

export OPAMP_REPO="${OPAMP_REPO:-/workspace/opamp}"
export RESULTS_DIR="${RESULTS_DIR:-/host-output}"
export CLEAN_ROOT="${CLEAN_ROOT:-/tmp/opamp-component-wheel-deployment}"

python /runner/run_component_wheel_deployment.py \
  --repo-root "$OPAMP_REPO" \
  --results-dir "$RESULTS_DIR" \
  --clean-root "$CLEAN_ROOT"
