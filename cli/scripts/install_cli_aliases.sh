#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLI_ENTRY="${CLI_ROOT}/main.py"

if [[ ! -f "${CLI_ENTRY}" ]]; then
  echo "Could not find CLI entrypoint: ${CLI_ENTRY}" >&2
  exit 1
fi

BLOCK_START="# >>> opamp-cli aliases >>>"
BLOCK_END="# <<< opamp-cli aliases <<<"
ALIAS_BLOCK="$(cat <<EOF
${BLOCK_START}
alias opamp-cli='python3 "${CLI_ENTRY}"'
alias opamp='python3 "${CLI_ENTRY}"'
${BLOCK_END}
EOF
)"

update_profile() {
  local profile_path="$1"
  mkdir -p "$(dirname "${profile_path}")"
  touch "${profile_path}"

  if grep -qF "${BLOCK_START}" "${profile_path}" && grep -qF "${BLOCK_END}" "${profile_path}"; then
    awk -v start="${BLOCK_START}" -v end="${BLOCK_END}" -v block="${ALIAS_BLOCK}" '
      BEGIN {in_block=0; replaced=0}
      $0 == start {
        if (!replaced) {
          print block
          replaced=1
        }
        in_block=1
        next
      }
      $0 == end {
        in_block=0
        next
      }
      !in_block {print}
      END {
        if (!replaced) {
          print block
        }
      }
    ' "${profile_path}" > "${profile_path}.tmp"
    mv "${profile_path}.tmp" "${profile_path}"
  else
    {
      echo
      echo "${ALIAS_BLOCK}"
    } >> "${profile_path}"
  fi

  echo "Updated aliases in: ${profile_path}"
}

update_profile "${HOME}/.bashrc"
update_profile "${HOME}/.zshrc"

echo "Done. Open a new shell session, or run:"
echo "  source ~/.bashrc"
