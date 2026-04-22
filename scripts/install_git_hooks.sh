#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

git -C "${REPO_ROOT}" config --local core.hooksPath .githooks
chmod +x "${REPO_ROOT}/.githooks/pre-commit"

GIT_COMMON_DIR="$(git -C "${REPO_ROOT}" rev-parse --git-common-dir)"
if [[ "${GIT_COMMON_DIR}" = /* ]]; then
  HOOKS_DIR="${GIT_COMMON_DIR}/hooks"
else
  HOOKS_DIR="${REPO_ROOT}/${GIT_COMMON_DIR}/hooks"
fi
mkdir -p "${HOOKS_DIR}"
LEGACY_PRE_COMMIT="${HOOKS_DIR}/pre-commit"
if [ -f "${LEGACY_PRE_COMMIT}" ] && ! grep -q "opamp-hook-shim" "${LEGACY_PRE_COMMIT}"; then
  echo "Detected existing custom ${LEGACY_PRE_COMMIT}; leaving it unchanged."
else
  cat > "${LEGACY_PRE_COMMIT}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# opamp-hook-shim: legacy .git/hooks fallback for GUI clients.
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec "${REPO_ROOT}/.githooks/pre-commit" "$@"
EOF
  chmod +x "${LEGACY_PRE_COMMIT}"
fi

echo "Configured git hooks path to ${REPO_ROOT}/.githooks"
echo "Verified fallback shim at ${LEGACY_PRE_COMMIT}"
