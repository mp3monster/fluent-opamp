# OpAMP Catalog Docs

Component-local documentation for the standalone OpAMP catalog package.

Current docs:
- component overview in `../README.md`
- freestanding example config in `../config/catalog-service.freestanding.example.json`
- test-case index in `./TEST_CASES.md`
- browser test harness in `../ui-tests/README.md`
- Playwright scenario notes in `../ui-tests/docs/`
- repository-wide catalog design notes remain in `../../docs/opamp_config_catalog_ui.md`

Packaging note:
- standalone `catalog-service` wheel builds warn when the separate `opamp-cli` component is not available
- the CLI is not bundled into the catalog-service wheel and should be installed/deployed independently when needed
