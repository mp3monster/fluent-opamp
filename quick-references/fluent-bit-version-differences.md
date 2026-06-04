# Fluent Bit Plugin Catalog Differences (All Plugins)

## Catalog Files
1. [fluent-bit-3.2.10-all-plugins-catalog.json](/mnt/d/dev/opamp/FLB-conf-ui/json-definitions/fluent-bit-3.2.10-all-plugins-catalog.json)
2. [fluent-bit-4.2.4-all-plugins-catalog.json](/mnt/d/dev/opamp/FLB-conf-ui/json-definitions/fluent-bit-4.2.4-all-plugins-catalog.json)
3. [fluent-bit-5.0.4-all-plugins-catalog.json](/mnt/d/dev/opamp/FLB-conf-ui/json-definitions/fluent-bit-5.0.4-all-plugins-catalog.json)

## Source Anchors
1. v3.2.10 release notes: https://fluentbit.io/announcements/v3.2.10/#release-notes-v3.2.10
2. v4.2.4 release notes: https://fluentbit.io/announcements/v4.2.4/#release-notes-v4.2.4
3. v5.0.4 release notes: https://fluentbit.io/announcements/v5.0.4/#release-notes-v5.0.4
4. v3.2 sitemap pages: https://docs.fluentbit.io/manual/3.2/sitemap-pages.xml
5. v4.2 sitemap pages: https://docs.fluentbit.io/manual/4.2/sitemap-pages.xml
6. v5.x sitemap pages: https://docs.fluentbit.io/manual/sitemap-pages.xml
7. Custom plugins section: https://docs.fluentbit.io/manual/administration/configuring-fluent-bit/yaml/plugins-section
8. Golang output plugins: https://docs.fluentbit.io/manual/fluent-bit-for-developers/golang-output-plugins
9. Wasm input plugins: https://docs.fluentbit.io/manual/development/wasm-input-plugins
10. Wasm filter plugins: https://docs.fluentbit.io/manual/fluent-bit-for-developers/wasm-filter-plugins

## Coverage Summary
| Version | Inputs | Filters | Outputs | Inputs w/ table | Filters w/ table | Outputs w/ table |
|---|---|---|---|---|---|---|
| 3.2.10 | 43 | 22 | 46 | 41/43 | 21/22 | 39/46 |
| 4.2.4 | 48 | 22 | 51 | 47/48 | 21/22 | 48/51 |
| 5.0.4 | 48 | 22 | 51 | 47/48 | 21/22 | 48/51 |

## 3.2.10 -> 4.2.4
### Inputs
1. Added: `blob, fluentbit-logs, gpu-metrics, prometheus-textfile, windows-system-statistics`
2. Removed: `none`
### Filters
1. Added: `none`
2. Removed: `none`
### Outputs
1. Added: `exit, parseable, plot, stackdriver_special_fields, udp`
2. Removed: `none`

## 4.2.4 -> 5.0.4
### Inputs
1. Added: `none`
2. Removed: `none`
### Filters
1. Added: `none`
2. Removed: `none`
### Outputs
1. Added: `none`
2. Removed: `none`

## 3.2.10 -> 5.0.4
### Inputs
1. Added: `blob, fluentbit-logs, gpu-metrics, prometheus-textfile, windows-system-statistics`
2. Removed: `none`
### Filters
1. Added: `none`
2. Removed: `none`
### Outputs
1. Added: `exit, parseable, plot, stackdriver_special_fields, udp`
2. Removed: `none`

## Custom Plugin Support (All Versions)
1. External shared-object plugin loading is represented in `custom_plugins.supported_loading.plugins_section`.
2. Golang external plugin support is represented for output plugins.
3. Wasm plugin support is represented for input/filter plugin types.

## Notes
1. The catalogs now include built-in `inputs`, `filters`, and `outputs` sections for each version, not just `forward`.
2. Field extraction uses plugin documentation tables; when a plugin page lacks a configuration table, the entry is still present with extraction status metadata.
