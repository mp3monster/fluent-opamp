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
9. [UI Testing](./ui-testing.md)
10. [Developer Tools](./dev-tools.md)
11. [Test Cases](./TEST_CASES.md)
12. [UI Framework Decision](./ui-framework-decision.md)

## What this service provides
- Versioned Fluent Bit catalog loading from config.
- Versioned Fluentd catalog loading from config, including nested section metadata.
- Schema compilation for configuration editing.
- Validation using schema/semantic checks plus pluggable rule profiles.
- YAML rendering for Fluent Bit and standard `.conf` rendering for Fluentd.
- Python-served schema-driven UI for plugin-driven config authoring.
- Read-only server mode controlled by backend configuration.
- Browser-based Playwright tests for UI behavior such as dropdowns, links, hover text, and partial file loads.
- Developer tooling for schema generation, reference generation, SBOM generation, and quality checks.

## Generated artifacts
- Fluent Bit and Fluentd version catalogs: `config-service/json-definitions/`
- Per-version catalog shards: `config-service/json-definitions/fluent-bit/<version>/` and `config-service/json-definitions/fluentd/<version>/`
- Versioned service/system option definitions: `config-service/json-definitions/`
- Generated runtime JSON Schemas: `config-service/json-schemas/`
- Per-version schema shards: `config-service/json-schemas/<config_type>/<version>/`

## Primary runtime entry points
- Backend app: `config-service/src/config_service/app.py`
- Backend package root: `config-service/src/config_service/`
- Python-served UI: `http://localhost:8080/config-service/ui`
- Local convenience scripts: `config-service/scripts`
- Developer tooling and generators: `config-service/dev-tools`
- Backend lint/test entrypoint: `config-service/dev-tools/run_backend_quality_checks.py`
- UI browser-test entrypoint: `config-service/dev-tools/run_ui_quality_checks.sh`
- Fluent Bit quick-reference generator: `config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py`
