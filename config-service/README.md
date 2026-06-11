# config-service

Standalone package for the config-service backend and Python-served UI used to view and edit observability agent configurations.

This package ships:
- the `config_service` Python package
- bundled HTML/CSS/JS UI assets
- bundled catalog and service definition JSON files, including versioned manifest shards
- generated runtime JSON schemas, including per-version plugin shards

Repository source layout:
- Python backend package: `src/config_service`
- developer tools: `dev-tools`
- operational scripts: `scripts`
- user documentation: `docs`

Run after installation:

```bash
config-service --config-path /path/to/config-service.json
```

Developer quality checks:

```bash
python3 config-service/dev-tools/run_backend_quality_checks.py
```

Browser UI quality checks:

```bash
config-service/dev-tools/run_ui_quality_checks.sh
```
