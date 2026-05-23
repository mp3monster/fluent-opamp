# catalog-service

Standalone package for the OpAMP configuration catalog backend and Python-served UI.

This component ships:
- the `catalog_service` Python package
- a standalone Quart app entrypoint
- provider integration via shared component entrypoints
- catalog unit tests

Catalog row behavior is configuration-driven:
- when a configured component endpoint advertises the config-service feature, clicking a row opens the config editor
- otherwise, clicking a row opens the built-in readonly file viewer

Repository source layout:
- Python backend package: `src/catalog_service`
- example configuration: `config`
- launcher script: `scripts`
- tests: `tests`
- browser tests: `ui-tests`
- user documentation: `docs`

Run after installation:

```bash
catalog-service --config-path /path/to/catalog-service.json
```

Standalone wheel creation checks whether the OpAMP CLI is available.
If the CLI is not detected in the workspace or as an installed distribution, the build prints
a warning because the CLI is packaged separately as `opamp-cli` and may need to be installed or
deployed alongside the catalog service.

Run from the repository:

```bash
PYTHONPATH=catalog-service/src python3 -m catalog_service
```

Temporary repo-local launcher while CLI tooling is still evolving:

```bash
python3 catalog-service/scripts/start_catalog_service.py
```

If you want the shared guided launcher experience, install the CLI separately and use:

```bash
opamp-cli --help
```

## Freestanding Example Config

Use [catalog-service.freestanding.example.json](/mnt/d/dev/opamp/catalog-service/config/catalog-service.freestanding.example.json)
as a starting point for a standalone deployment that scans folders outside the provider runtime.

The example assumes a local layout like:

```text
your-workspace/
  catalog-service.freestanding.example.json
  configs/
    fluent-bit/
    fluentd/
    shared/
```

Run with the example config:

```bash
catalog-service --config-path /path/to/catalog-service.freestanding.example.json
```

Run the repo-local launcher with an explicit config path:

```bash
python3 catalog-service/scripts/start_catalog_service.py --config-path /path/to/catalog-service.freestanding.example.json
```

The configured source folders are resolved relative to the config file location when they exist there,
which makes the example suitable for a copied freestanding workspace.

## UI Test Coverage

Standalone browser coverage for the catalog UI lives in `ui-tests/`.

The current Playwright scenarios cover:

- freestanding catalog with config-service available
- freestanding catalog without config-service available
- feature-menu navigation to the config-service UI
- row-click navigation into the config editor
- row-click fallback into the readonly file viewer

Scenario maintenance notes for each Playwright test live in `ui-tests/docs/`.
