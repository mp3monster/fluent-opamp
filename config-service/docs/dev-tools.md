# Developer Tools

This page summarizes developer-facing helper scripts in `config-service/dev-tools`.

## Fluent Bit Schema Quick Reference Generator

Script:
- [generate_fluentbit_schema_quick_reference.py](../dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py)

Purpose:
1. Reads the local Fluent Bit JSON schema files
2. Generates Markdown quick references for:
   - `env` environment variables
   - `upstream_servers` upstream server groups
   - pipeline plugins
3. Produces grouped pipeline sections for:
   - `inputs`
   - `filters`
   - `outputs`
4. Includes:
   - alphabetical plugin jump lists
   - plugin anchors
   - mandatory flags
   - default values
   - descriptions
   - hyperlinks to Fluent Bit documentation

The schema input files can be either direct JSON payloads or manifest files that point to
versioned shard trees such as `json-schemas/fluentbit/3.2.10/inputs/*.json`. Individual
plugin shard files may use JSON Schema `$ref` to shared version-local fragments such as
`json-schemas/fluentbit/3.2.10/processors.json`.

Inputs:
1. [fluentbit-3.2.10-config-schema.json](../json-schemas/fluentbit-3.2.10-config-schema.json)
2. [fluentbit-4.2.4-config-schema.json](../json-schemas/fluentbit-4.2.4-config-schema.json)
3. [fluentbit-5.0.4-config-schema.json](../json-schemas/fluentbit-5.0.4-config-schema.json)

Outputs:
1. [fluentbit-3-2-10-schema-quick-reference.md](../../quick-references/fluentbit-3-2-10-schema-quick-reference.md)
2. [fluentbit-4-2-4-schema-quick-reference.md](../../quick-references/fluentbit-4-2-4-schema-quick-reference.md)
3. [fluentbit-5-0-4-schema-quick-reference.md](../../quick-references/fluentbit-5-0-4-schema-quick-reference.md)

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py
```

Optional:

```bash
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --help
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --version 4.2.4
python3 config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py --source-dir config-service/json-schemas --output-dir quick-references
```

What to expect:
1. The script overwrites the generated Markdown file
2. The output is deterministic for the current schema contents
3. Any formatting updates should be made in the generator, then regenerated

Recommended verification:

```bash
python3 -m ruff check config-service/dev-tools/quick-references/generate_fluentbit_schema_quick_reference.py
```

When to use it:
1. After schema regeneration for Fluent Bit `3.2.10`, `4.2.4`, or `5.0.4`
2. After adjusting schema metadata such as descriptions, defaults, or required flags
3. When refreshing the quick references in `quick-references`

## Fluent Bit Plugin Attribute Reference Generator

Script:
- [generate_fluentbit_plugin_attribute_reference.py](../dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py)

Purpose:
1. Reads the local Fluent Bit catalog JSON files
2. Generates Markdown attribute reference files for each Fluent Bit version
3. Produces grouped sections for:
   - `inputs`
   - `filters`
   - `outputs`

The catalog input files can be either direct JSON payloads or manifest files that point to
versioned shard trees such as `json-definitions/fluent-bit/3.2.10/outputs/*.json`.

Inputs:
1. [fluent-bit-3.2.10-all-plugins-catalog.json](../json-definitions/fluent-bit-3.2.10-all-plugins-catalog.json)
2. [fluent-bit-4.2.4-all-plugins-catalog.json](../json-definitions/fluent-bit-4.2.4-all-plugins-catalog.json)
3. [fluent-bit-5.0.4-all-plugins-catalog.json](../json-definitions/fluent-bit-5.0.4-all-plugins-catalog.json)

Outputs:
1. [fluentbit-3-2-10-plugin-attribute-reference.md](../../quick-references/fluentbit-3-2-10-plugin-attribute-reference.md)
2. [fluentbit-4-2-4-plugin-attribute-reference.md](../../quick-references/fluentbit-4-2-4-plugin-attribute-reference.md)
3. [fluentbit-5-0-4-plugin-attribute-reference.md](../../quick-references/fluentbit-5-0-4-plugin-attribute-reference.md)

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py
```

Optional:

```bash
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py --help
python3 config-service/dev-tools/quick-references/generate_fluentbit_plugin_attribute_reference.py --source-dir config-service/json-definitions --output-dir quick-references
```

## Fluent Bit Plugin Name Checker

Script:
- [check_fluentbit_plugin_names.py](../dev-tools/check_fluentbit_plugin_names.py)

Purpose:
1. Reads Fluent Bit plugin definition files from one named folder such as `json-definitions/fluent-bit/3.2.10/inputs`
2. Fetches each plugin's documentation page from its `doc_url`
3. Extracts the real Fluent Bit config `Name` from page content such as:
   - `[INPUT] Name stdin`
   - `[FILTER] Name rewrite_tag`
   - `[output:stdout:stdout.0]`
4. Logs every check and any applied rename
5. Optionally updates matching catalog manifests and schema shard files

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/check_fluentbit_plugin_names.py config-service/json-definitions/fluent-bit/3.2.10/inputs
```

Apply changes:

```bash
python3 config-service/dev-tools/check_fluentbit_plugin_names.py --apply config-service/json-definitions/fluent-bit/3.2.10/inputs
```
