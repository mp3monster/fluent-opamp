# Batch Scenario Configurations

Place additional JSON scenario files in this folder.

Each scenario can override the defaults used by:
- `config-service/dev-tools/playwright_chapter_batch_runner.mjs`

Current supported keys:
- `yamlExtensions`: array of file extensions to process.
- `saveSuffix`: suffix appended to saved files.
- `additionalPluginAttribute.pluginName`: plugin name to target for optional attribute mutation.
- `additionalPluginAttribute.field`: optional field to add.
- `additionalPluginAttribute.value`: value to assign after adding.

Use one scenario file per validation profile, then pass it to the container runner with:

```bash
-e PLAYWRIGHT_BATCH_CONFIG=/workspace/opamp/config-service/dev-tools/playwright-batch-config/scenarios/<name>.json
```
