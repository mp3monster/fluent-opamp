# OpAMP Developer Tools

`opamp-dev-tools` is the consolidated developer CLI for repository maintenance
work such as schema validation, version updates, packaging, SBOM generation,
test execution, security checks, and certificate helpers.

Run from the repository root during development:

```bash
python3 dev-tools/main.py --help
python3 dev-tools/main.py build artefact all
python3 dev-tools/main.py build js-complexity
python3 dev-tools/main.py dev validate-schemas
```

Extension guidance lives in `dev-tools/docs/CLI_EXTENSION_GUIDE.md`.
