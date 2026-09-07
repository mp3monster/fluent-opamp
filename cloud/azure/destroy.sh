#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-opamp-regression-rg}"
NO_WAIT="${NO_WAIT:-true}"

if [[ "$NO_WAIT" == "true" ]]; then
  az group delete --name "$RESOURCE_GROUP" --yes --no-wait
else
  az group delete --name "$RESOURCE_GROUP" --yes
fi
