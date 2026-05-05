# Config-Service User Documentation

This folder contains user-facing documentation for running, configuring, and extending `config-service`.

## Contents
1. [Quickstart](./quickstart.md)
2. [Configuration Reference](./configuration.md)
3. [UI User Guide](./ui-user-guide.md)
4. [Catalog Management](./catalog-management.md)
5. [Custom Validation Logic](./custom-validation.md)
6. [API Reference](./api-reference.md)
7. [Troubleshooting](./troubleshooting.md)
8. [Standalone Packaging](./standalone-packaging.md)

## What this service provides
- Versioned Fluent Bit catalog loading from config.
- Versioned Fluentd catalog loading from config, including nested section metadata.
- Schema compilation for configuration editing.
- Validation using schema/semantic checks plus pluggable rule profiles.
- YAML rendering for Fluent Bit and standard `.conf` rendering for Fluentd.
- Python-served schema-driven UI for plugin-driven config authoring.
- Read-only server mode controlled by backend configuration.

## Generated artifacts
- Fluent Bit and Fluentd version catalogs: `config-service/json-definitions/`
- Versioned service/system option definitions: `config-service/json-definitions/`
- Generated runtime JSON Schemas: `config-service/json-schemas/`

## Primary runtime entry points
- Backend app: `config-service/config_service/app.py`
- Python-served UI: `http://localhost:8080/config-service/ui`
- Local convenience scripts: `config-service/scripts`
- Developer tooling and generators: `config-service/dev-tools`
- Backend lint/test entrypoint: `config-service/dev-tools/run_backend_quality_checks.py`
