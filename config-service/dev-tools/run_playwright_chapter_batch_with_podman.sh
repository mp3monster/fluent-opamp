#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_NAME="${PLAYWRIGHT_BATCH_IMAGE:-config-service-ui-playwright-batch:latest}"
CONTAINER_NAME="${PLAYWRIGHT_BATCH_CONTAINER_NAME:-config-service-ui-playwright-batch-runner}"
DOCKERFILE_PATH="${PLAYWRIGHT_BATCH_DOCKERFILE:-tests/test-containers/config-service-ui-playwright-batch/Dockerfile}"
RESULTS_DIR="${PLAYWRIGHT_BATCH_RESULTS_DIR:-${ROOT_DIR}/config-service/dev-tools/playwright-batch-artifacts}"

if ! command -v podman >/dev/null 2>&1; then
  echo "podman is not available in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to build the config-service wheel." >&2
  exit 1
fi

echo "Building latest config-service wheel"
cd "${ROOT_DIR}/config-service"
python3 -m pip install --upgrade pip build >/dev/null
python3 -m build --wheel --outdir dist

cd "${ROOT_DIR}"

echo "Removing existing container instance (if present): ${CONTAINER_NAME}"
podman rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "Building container image: ${IMAGE_NAME}"
podman build -f "${DOCKERFILE_PATH}" -t "${IMAGE_NAME}" .

mkdir -p "${RESULTS_DIR}"

echo "Running batch validation container"
set +e
podman run --name "${CONTAINER_NAME}" --rm -t \
  --ipc=host \
  -e OPAMP_REPO=/workspace/opamp \
  -e CONFIG_SERVICE_DIR=/workspace/opamp/config-service \
  -e CONFIG_SERVICE_CONFIG_PATH=/workspace/opamp/config-service/config/config-service.json \
  -e WHEEL_DIR=/workspace/opamp/config-service/dist \
  -e RESULTS_DIR=/workspace/opamp/config-service/dev-tools/playwright-batch-artifacts \
  -e PLAYWRIGHT_BATCH_CONFIG=/workspace/opamp/config-service/dev-tools/playwright-batch-config/default-batch-config.json \
  -v "${ROOT_DIR}:/workspace/opamp" \
  "${IMAGE_NAME}"
RUN_EXIT=$?
set -e

if [ "${RUN_EXIT}" -ne 0 ]; then
  echo "Batch validation completed with issues. See: ${RESULTS_DIR}" >&2
else
  echo "Batch validation completed successfully. Artifacts: ${RESULTS_DIR}"
fi

exit "${RUN_EXIT}"
