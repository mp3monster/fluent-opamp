# Standalone Packaging

## Standalone config file
The standalone service now prefers:
1. `config-service/config/config-service.json`

That file stores config-service runtime settings under:
1. `config-tool`

Example:
```json
{
  "config-tool": {
    "web_port": 8080,
    "ui_base_css_path": "/config-service/ui/assets/config_ui.css",
    "ui_css_overrides": [],
    "ui_collapsed_sections": [
      "environment_variables",
      "metadata_environment_variables",
      "upstream_servers",
      "parsers",
      "service",
      "rendered_configuration"
    ],
    "read_only": false
  }
}
```

For the complete list of supported `ui_collapsed_sections` values and aliases, see [Configuration Reference](./configuration.md).

## Build the wheel
From repository root:
```bash
cd config-service
python3 -m build --wheel
```

Output:
1. `config-service/dist/*.whl`

## Install and run standalone
```bash
pip install config-service/dist/config_service-0.1.0-py3-none-any.whl
config-service --config-path /path/to/config-service.json
```

## Generate the SBOM
From repository root:
```bash
python3 config-service/dev-tools/generate_sbom.py
```

Output:
1. `config-service/sbom/config-service-sbom.cdx.json`
