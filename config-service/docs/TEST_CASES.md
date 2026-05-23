# Config Service Test Cases

This document is the maintained test-case index for `config-service`.
Each test module should reference this file so the documented scenarios evolve with the code.

## Agent Validation Tests

### `config-service/tests/test_agent_validation_service.py`
- Covers validation-agent registry resolution, exact-version and fallback selection, temporary-file mode, dry-run eligibility, placeholder rejection logging, and adapter unhappy-path logging for Fluent Bit and Fluentd.

## API Runtime and Catalog Tests

### `config-service/tests/test_api_runtime_config.py`
- Covers runtime-config precedence for web port, component entry points, UI assets, read-only mode, log level, collapsed sections, and external validation agent configuration.

### `config-service/tests/test_api_catalog_and_schema.py`
- Covers health/version endpoints, catalog/service-definition/schema behavior, config-type aliases, catalog invariants, and normalized request-validation errors.

## UI and Editor Tests

### `config-service/tests/test_api_ui.py`
- Covers client error logging, UI route toggles, CSS overrides, collapsed-section injection, help pages, dev-mode cache behavior, UI file preparation, and server-side source-file loading.

## Fluent Bit Parsing, Validation, and Rendering Tests

### `config-service/tests/test_api_fluentbit_parse.py`
- Covers Fluent Bit YAML parsing, native route mapping, parser loading, recursive include handling, include merge validation, environment metadata round-trips, upstream server round-trips, ignored-section reporting, and empty-file rejection.

### `config-service/tests/test_api_fluentbit_validation.py`
- Covers Fluent Bit API validation behavior, builtin and custom parser references, type enforcement, rule adapters, Lua/SQL validation normalization, logging on unhappy paths, and selector-related validation scenarios.

### `config-service/tests/test_api_render_yaml.py`
- Covers YAML rendering order, route translation, include rendering, empty-section omission, backend-composed rendered output, and config-service header generation.

## Fluentd Parsing, Validation, and Rendering Tests

### `config-service/tests/test_api_fluentd.py`
- Covers Fluentd parse/render round-trips, schema support, validation acceptance rules, parse failures, empty-file handling, invalid render requests, and rendered-output composition.

## External Agent Validation API Tests

### `config-service/tests/test_api_agent_validation.py`
- Covers dry-run availability filtering, dry-run rejection when disabled, and successful dry-run execution when enabled.
