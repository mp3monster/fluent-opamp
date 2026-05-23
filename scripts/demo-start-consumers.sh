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

if [[ -t 1 ]]; then
  printf '\033]0;%s\007' "OpAMP Demo Start Consumers"
fi

launch_in_terminal_window() {
  local script_path="$1"
  local script_name
  script_name="$(basename "${script_path}")"

  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -lc "cd '${REPO_ROOT}' && '${script_path}'" &
    return
  fi

  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "cd '${REPO_ROOT}' && '${script_path}'" &
    return
  fi

  if command -v konsole >/dev/null 2>&1; then
    konsole --noclose -e bash -lc "cd '${REPO_ROOT}' && '${script_path}'" &
    return
  fi

  if command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --command "bash -lc 'cd \"${REPO_ROOT}\" && \"${script_path}\"'" &
    return
  fi

  if command -v cmd.exe >/dev/null 2>&1; then
    local cmd_script
    cmd_script="${script_path%.sh}.cmd"
    if [[ -f "${cmd_script}" ]]; then
      cmd.exe /c start "OpAMP ${script_name}" cmd /k "cd /d \"${REPO_ROOT}\" && call \"${cmd_script}\"" >/dev/null 2>&1
      return
    fi
  fi

  echo "No terminal launcher detected for ${script_name}; running in background."
  nohup bash -lc "cd '${REPO_ROOT}' && '${script_path}'" >/dev/null 2>&1 &
}

scripts_to_launch=(
  "${SCRIPT_DIR}/run_consumer_sim_start.sh"
  "${SCRIPT_DIR}/run_fluentbit_supervisor.sh"
  "${SCRIPT_DIR}/run_fluentd_supervisor.sh"
)

for launch_script in "${scripts_to_launch[@]}"; do
  if [[ ! -f "${launch_script}" ]]; then
    echo "Required script not found: ${launch_script}"
    exit 1
  fi
  echo "Launching $(basename "${launch_script}")"
  launch_in_terminal_window "${launch_script}"
done

echo "Consumer demo launch requested for simulator + fluentbit + fluentd clients."
