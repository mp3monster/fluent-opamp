# Configuration Reference

## Overview
`config-service` uses JSON configuration files for:
1. Versioned catalog selection
2. Validation profile/ruleset selection

## Files
- Catalog registry: `config-service/config/catalog-registry.json`
- Validation registry: `config-service/config/validation-rules-registry.json`
- Service registry: `config-service/config/service-registry.json`

## Environment variables
- `CONFIG_SERVICE_WEB_PORT`
  - Optional integer override for the config-service listen port.
  - Takes precedence over JSON file settings.
- `CONFIG_SERVICE_UI_BASE_CSS_PATH`
  - Optional URL/path override for the primary UI stylesheet.
  - Takes precedence over JSON file settings.
- `APP_ENABLE_DEV_FEATURES`
  - Truthy values: `1`, `true`, `yes`, `on`
  - Controls developer-only UI features (for example, `Reload UI` button visibility)
- `CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH`
  - Optional single CSS URL/path loaded after default UI CSS.
- `CONFIG_SERVICE_UI_CSS_OVERRIDES`
  - Optional comma-separated CSS URLs/paths loaded after default UI CSS.
- Authentication variables (shared with OpAMP provider auth model):
  - `UI_AUTH_MODE` (`disabled`, `static`, `jwt`)
  - `UI_AUTH_STATIC_TOKEN`
  - `UI_AUTH_JWT_ISSUER`
  - `UI_AUTH_JWT_AUDIENCE`
  - `UI_AUTH_JWT_JWKS_URL`
  - `UI_AUTH_JWT_LEEWAY_SECONDS`

## Catalog registry format
Path: `config-service/config/catalog-registry.json`

Example:
```json
{
  "registry_version": "1.0.0",
  "default_fluent_bit_version": "5.0.4",
  "catalogs": {
    "3.2.10": "config-service/json-definitions/fluent-bit-3.2.10-all-plugins-catalog.json",
    "4.2.4": "config-service/json-definitions/fluent-bit-4.2.4-all-plugins-catalog.json",
    "5.0.4": "config-service/json-definitions/fluent-bit-5.0.4-all-plugins-catalog.json"
  }
}
```

Rules:
1. `catalogs` must be a non-empty object.
2. Each version key must map to a readable JSON file path.
3. `default_fluent_bit_version` should point to a key inside `catalogs`.

## Service registry format
Path: `config-service/config/service-registry.json`

Example:
```json
{
  "registry_version": "1.0.0",
  "default_fluent_bit_version": "5.0.4",
  "service_definitions": {
    "3.2.10": "config-service/json-definitions/fluent-bit-3.2.10-service-options.json",
    "4.2.4": "config-service/json-definitions/fluent-bit-4.2.4-service-options.json",
    "5.0.4": "config-service/json-definitions/fluent-bit-5.0.4-service-options.json"
  }
}
```

Rules:
1. `service_definitions` must be a non-empty object.
2. Each version maps to a JSON file that defines:
   1. `section: service`
   2. `cardinality.maximum: 1`
   3. `options[]` metadata for UI and validation typing.

## Validation registry format
Path: `config-service/config/validation-rules-registry.json`

Key sections:
1. `default_profile`
2. `profiles`
3. `rulesets`
4. `version_overrides`

Behavior:
1. A profile selects one or more named rulesets.
2. Each ruleset points to an adapter via `adapter` (for example `builtin.data_type_enforcement`).
3. `version_overrides.<version>.additional_rulesets` adds version-specific rule evaluation.

## Backend mode
- `standalone`: launched directly by `config_service/app.py`
- `embedded`: mounted into OpAMP provider via `config_service/opamp_integration.py`

## Listen port resolution
`config-service` resolves its standalone listen port in this order:
1. Environment variable `CONFIG_SERVICE_WEB_PORT`
2. `config_service.web_port` in the JSON config file referenced by `OPAMP_CONFIG_PATH`
3. `provider.webui_port` in that same JSON config file
4. Default `8080`

Default config file path:
- `config/opamp.json`

Example:
```json
{
  "config_service": {
    "web_port": 8090,
    "ui_base_css_path": "/ui/assets/web_ui.css"
  }
}
```

## Authentication behavior
1. Embedded mode reuses OpAMP provider non-OpAMP HTTP auth checks.
2. Standalone mode also reuses provider auth helpers when `provider/src` is importable.
3. Unauthorized requests return `401` and include `WWW-Authenticate: Bearer ...`.

## UI CSS integration (OpAMP look and feel)
The browser UI can load shared OpAMP stylesheets using:
1. Environment variable `CONFIG_SERVICE_UI_BASE_CSS_PATH` for the primary stylesheet.
2. JSON config key `config_service.ui_base_css_path` in `config/opamp.json`.
3. Environment variable `CONFIG_SERVICE_UI_CSS_OVERRIDE_PATH` for one additional override path.
4. Environment variable `CONFIG_SERVICE_UI_CSS_OVERRIDES` for multiple additional override paths.
5. App config override key `CONFIG_SERVICE_UI_CSS_OVERRIDES` (list or comma-separated string).

Fallback theme remains available when no custom base stylesheet is provided.
