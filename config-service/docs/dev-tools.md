# Developer Tools

This page summarizes developer-facing helper scripts in `config-service/dev-tools`.

## Fluent Bit 5.0.4 Schema Quick Reference Generator

Script:
- [generate_fluentbit_schema_quick_reference.py](/mnt/d/dev/opamp/config-service/dev-tools/generate_fluentbit_schema_quick_reference.py)

Purpose:
1. Reads the local Fluent Bit 5.0.4 JSON schema
2. Generates a Markdown quick reference for pipeline plugins
3. Produces grouped sections for:
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

Input:
- [fluentbit-5.0.4-config-schema.json](/mnt/d/dev/opamp/config-service/json-schemas/fluentbit-5.0.4-config-schema.json)

Output:
- [fluent-bit-5.0.4-schema-quick-reference.md](/mnt/d/dev/opamp/config-service/dev-notes/fluent-bit-5.0.4-schema-quick-reference.md)

Run it:

```bash
cd /mnt/d/dev/opamp
python3 config-service/dev-tools/generate_fluentbit_schema_quick_reference.py
```

What to expect:
1. The script overwrites the generated Markdown file
2. The output is deterministic for the current schema contents
3. Any formatting updates should be made in the generator, then regenerated

Recommended verification:

```bash
python3 -m ruff check config-service/dev-tools/generate_fluentbit_schema_quick_reference.py
```

When to use it:
1. After schema regeneration for Fluent Bit `5.0.4`
2. After adjusting schema metadata such as descriptions, defaults, or required flags
3. When refreshing the developer reference in `dev-notes`
