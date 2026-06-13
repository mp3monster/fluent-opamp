#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="$MCP_DIR/src:$PYTHONPATH"
else
  export PYTHONPATH="$MCP_DIR/src"
fi

exec "$PYTHON_BIN" -m opamp_mcp_config.build_tool "$@"
