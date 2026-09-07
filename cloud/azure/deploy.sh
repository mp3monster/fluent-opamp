#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-opamp-regression-rg}"
LOCATION="${LOCATION:-uksouth}"
PARAMETERS_FILE="${PARAMETERS_FILE:-cloud/azure/parameters.example.json}"
TEMPLATE_FILE="${TEMPLATE_FILE:-cloud/azure/mainTemplate.json}"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$TEMPLATE_FILE" \
  --parameters "@$PARAMETERS_FILE"
