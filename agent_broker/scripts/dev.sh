#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export BROKER_CONFIG_PATH="${BROKER_CONFIG_PATH:-./opamp_broker/config/broker.ui_responses.json}"
python -m opamp_broker.broker_app
