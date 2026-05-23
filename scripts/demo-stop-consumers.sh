#!/usr/bin/env bash
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SEMAPHORE_PATH="${REPO_ROOT}/OpAMPSupervisor.signal"

if [[ -t 1 ]]; then
  printf '\033]0;%s\007' "OpAMP Demo Stop Consumers"
fi

echo "Stopping consumer simulator launcher instances..."
if [[ -f "${SCRIPT_DIR}/run_consumer_sim_stop.sh" ]]; then
  (
    cd "${REPO_ROOT}"
    "${SCRIPT_DIR}/run_consumer_sim_stop.sh"
  ) || true
fi

echo "Requesting graceful shutdown for fluentbit/fluentd consumer clients via semaphore..."
touch "${SEMAPHORE_PATH}"

# Give heartbeat loops a chance to observe semaphore and exit.
sleep 2

if [[ -f "${SCRIPT_DIR}/terminate_fluent_bit.sh" ]]; then
  "${SCRIPT_DIR}/terminate_fluent_bit.sh" || true
fi

# Fallback cleanup for supervisor client processes that did not exit yet.
pkill -TERM -f "opamp_consumer\.fluentbit_client" >/dev/null 2>&1 || true
pkill -TERM -f "opamp_consumer\.fluentd_client" >/dev/null 2>&1 || true

echo "Stop request complete."
echo "Note: ${SEMAPHORE_PATH} is intentionally left in place until next launch removes it."
