# Troubleshooting

## Backend fails to start
Check:
1. `catalog-registry.json` paths are valid.
2. `validation-rules-registry.json` references known adapters.
3. Python dependencies are installed.

## Frontend cannot load versions
Check:
1. Backend is running on expected host/port.
2. Browser can reach `/config-service/api/v1/versions`.
3. Console/network tab for CORS/proxy issues.

## Validation returns unknown plugin errors
Check:
1. Selected version is correct for the plugin.
2. Plugin name exists in catalog section.
3. Field names match catalog metadata.

## Optional field not retained in UI
Check:
1. Field was added through optional attribute selector.
2. Field was not removed by dependency rules or manual removal.

## Logs and runtime state
- Script logs: `config-service/.run/logs/`
- Foreground launcher state: use the terminal running `dev-up` and stop with `Ctrl+C`

## Common cleanup
1. Stop stack: `Ctrl+C` in the terminal running `scripts/dev-up.sh` (or `.cmd` on Windows)
2. Remove stale state: delete `config-service/.run/`
3. Restart stack: `scripts/dev-up.sh`
