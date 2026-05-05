# config-service

Standalone package for the config-service backend and Python-served UI used to view and edit observability agent configurations.

This package ships:
- the `config_service` Python package
- bundled HTML/CSS/JS UI assets
- bundled catalog and service definition JSON files
- generated runtime JSON schemas

Run after installation:

```bash
config-service --config-path /path/to/config-service.json
```

Developer quality checks:

```bash
python3 config-service/dev-tools/run_backend_quality_checks.py
```
