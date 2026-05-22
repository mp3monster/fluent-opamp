# OpAMP Config Catalog UI

## Overview

The provider can host a **Config Catalog** page that indexes configuration files from configured folders and displays metadata extracted from top comment blocks.

- UI route: `/catalog` (default)
- Help route: `/catalog/help` (default)
- Data route: `/catalog/api/files` (default)

The page is added to the provider feature menu when enabled.

## Configuration

Configure in `opamp.json` under top-level `opamp.config_catalog`:

```json
{
  "opamp": {
    "config_catalog": {
      "enabled": true,
      "menu_label": "Config Catalog",
      "route_path": "/catalog",
      "help_path": "/catalog/help",
      "ui_base_css_path": "/config-service/ui/assets/config_ui.css",
      "sources": [
        {
          "folder": "config-service/json-definitions",
          "extensions": [".json", ".yaml", ".yml", ".conf"]
        }
      ]
    }
  }
}
```

### Fields

- `enabled`: enables/disables the feature.
- `menu_label`: label used in provider feature dropdown.
- `route_path`: base UI route.
- `help_path`: route for catalog help content.
- `ui_base_css_path`: CSS path used to align appearance with config-service.
- `sources`: folders and extension filters to scan.

## Header Metadata Format

The catalog parser extracts metadata from top comment lines using:

- `config-service: key=value`

Example:

```text
# config-service: config_type=fluentbit
# config-service: version=5.0.4
# config-service: config_version=release-27
```

All discovered keys become table columns.

## Provider UI Feature Menu Integration

Provider feature dropdown entries are configuration-driven from `component-entry-points.quart` entries that include `label` and `url`.

Example:

```json
{
  "component-entry-points": {
    "quart": [
      {
        "entry_point": "config_service.opamp_integration:register_config_service_feature",
        "label": "Config Service UI",
        "url": "/config-service/ui",
        "enabled": true
      }
    ]
  }
}
```

## Help

Catalog help page:

- `/catalog/help`
