# OpAMP Config Catalog Service Prompt

## Purpose

Use this prompt to describe the provider-side config catalog feature intent and boundaries when implementing or extending it.

## Prompt

Build and maintain an OpAMP provider feature called **Config Catalog** that is fully configuration-driven.

Requirements:

1. Read catalog configuration from `opamp.config_catalog` in `opamp.json`.
2. Scan configured folders and include only files matching configured extensions.
3. For each file, inspect the top comment block and extract `config-service: key=value` metadata fields.
4. Build a table view showing:
   - folder location
   - filename
   - last edited timestamp (filesystem-derived)
   - one column per discovered metadata key
5. Leave metadata cells blank when values are missing.
6. Expose a catalog API endpoint returning rows + dynamic columns.
7. Expose a catalog UI and help page.
8. Reuse config-service visual language:
   - base CSS
   - logo
   - footer conventions
9. Keep UI behavior aligned with provider main table patterns:
   - sortable columns
   - client-side filtering
   - pagination
10. Provide tests:
    - unit tests for scanner/metadata extraction
    - endpoint tests for catalog API/UI routes
    - Playwright tests for navigation and rendered table expectations

## Non-goals

- Do not validate file content semantics.
- Do not mutate scanned files.
- Do not require metadata fields to exist.

## Notes

- Configuration must support adding future catalog features without code rewrites.
- Missing/invalid source folders should fail softly (skip source, continue).
