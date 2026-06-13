import fs from "node:fs/promises";
import fssync from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";
import yaml from "js-yaml";

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const value = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
    args[key] = value;
  }
  return args;
}

function compareVersions(left, right) {
  const a = String(left || "").split(".").map((part) => Number(part) || 0);
  const b = String(right || "").split(".").map((part) => Number(part) || 0);
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i += 1) {
    const diff = (a[i] || 0) - (b[i] || 0);
    if (diff !== 0) {
      return diff;
    }
  }
  return 0;
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function flattenPaths(value, prefix = "$") {
  const out = new Set();
  function walk(node, current) {
    if (Array.isArray(node)) {
      if (node.length === 0) {
        out.add(current);
        return;
      }
      node.forEach((item, index) => {
        walk(item, `${current}[${index}]`);
      });
      return;
    }
    if (node && typeof node === "object") {
      const keys = Object.keys(node);
      if (keys.length === 0) {
        out.add(current);
        return;
      }
      keys.forEach((key) => {
        walk(node[key], `${current}.${key}`);
      });
      return;
    }
    out.add(current);
  }
  walk(value, prefix);
  return out;
}

async function walkFiles(rootDir) {
  const discovered = [];
  async function recurse(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await recurse(absolute);
      } else {
        discovered.push(absolute);
      }
    }
  }
  await recurse(rootDir);
  return discovered;
}

function hasChapterSegment(filePath) {
  const normalized = filePath.replace(/\\/g, "/");
  return /\/Chapter[^/]*\//i.test(normalized);
}

async function discoverYamlFiles(sourceRoot, config) {
  const allFiles = await walkFiles(sourceRoot);
  const extensions = Array.isArray(config.yamlExtensions) && config.yamlExtensions.length > 0
    ? config.yamlExtensions.map((ext) => String(ext).toLowerCase())
    : [".yaml", ".yml"];

  return allFiles
    .filter((filePath) => hasChapterSegment(filePath))
    .filter((filePath) => extensions.includes(path.extname(filePath).toLowerCase()))
    .sort((left, right) => left.localeCompare(right));
}

function loadYamlFile(filePath) {
  const raw = fssync.readFileSync(filePath, "utf-8");
  const docs = yaml.loadAll(raw);
  if (!docs || docs.length === 0) {
    return {};
  }
  if (docs.length === 1) {
    return docs[0] || {};
  }
  return docs;
}

function safeYamlParse(text) {
  try {
    const parsed = yaml.load(text);
    return parsed || {};
  } catch (_err) {
    return {};
  }
}

async function ensurePanelOpenIfCollapsed(page, toggleSelector) {
  const toggle = page.locator(toggleSelector);
  if ((await toggle.count()) === 0) {
    return;
  }
  const label = String((await toggle.first().textContent()) || "").trim().toLowerCase();
  if (label === "open") {
    await toggle.first().click();
  }
}

async function uiLatestVersion(page) {
  const options = await page.locator("#version-select option").allTextContents();
  const normalized = options.map((entry) => String(entry || "").trim()).filter(Boolean);
  if (normalized.length === 0) {
    return "";
  }
  normalized.sort(compareVersions);
  return normalized[normalized.length - 1];
}

async function addMetadataVariable(page, key, value) {
  await page.locator("#metadata-env-key-input").fill(String(key));
  await page.locator("#metadata-env-value-input").fill(String(value));
  await page.getByRole("button", { name: "Add Metadata Variable" }).click();
}

async function annotatePlugins(page, suffix) {
  const cards = page.locator("#plugin-list .plugin-card");
  const count = await cards.count();
  for (let i = 0; i < count; i += 1) {
    const card = cards.nth(i);
    const commentToggle = card.locator("button[aria-label*='plugin comment editor']");
    if ((await commentToggle.count()) > 0) {
      await commentToggle.first().click();
      const textarea = card.locator(".comment-editor textarea");
      if ((await textarea.count()) > 0) {
        await textarea.first().fill(`batch-comment ${suffix} plugin-${i + 1}`);
      }
    }

    const controls = card.locator(".field-grid .field-row input:not([disabled]), .field-grid .field-row textarea:not([disabled]), .field-grid .field-row select:not([disabled])");
    const controlCount = await controls.count();
    for (let controlIndex = 0; controlIndex < controlCount; controlIndex += 1) {
      if (controlIndex % 2 === 0) {
        continue;
      }
      const control = controls.nth(controlIndex);
      const tagName = await control.evaluate((element) => element.tagName.toLowerCase());
      if (tagName === "select") {
        const optionValues = await control.locator("option").evaluateAll((nodes) => nodes.map((node) => node.value).filter(Boolean));
        if (optionValues.length > 1) {
          await control.selectOption(optionValues[optionValues.length - 1]);
        }
      } else {
        const current = (await control.inputValue()) || "";
        await control.fill(`${current} batch-${controlIndex}`.trim());
      }
    }
  }
  return count;
}

async function addAdditionalPluginAttribute(page, config, result) {
  const cfg = config.additionalPluginAttribute || {};
  const pluginName = String(cfg.pluginName || "").trim();
  const field = String(cfg.field || "").trim();
  const value = cfg.value;
  if (!pluginName || !field) {
    result.warnings.push("additionalPluginAttribute not configured; skipping optional attribute mutation.");
    return;
  }

  const cards = page.locator("#plugin-list .plugin-card");
  const count = await cards.count();
  let targetCard = null;
  for (let i = 0; i < count; i += 1) {
    const card = cards.nth(i);
    const heading = String((await card.locator(".plugin-head strong").first().textContent()) || "");
    if (heading.toLowerCase().includes(pluginName.toLowerCase())) {
      targetCard = card;
      break;
    }
  }

  if (!targetCard) {
    result.warnings.push(`No plugin card found for '${pluginName}'.`);
    return;
  }

  const optionalSelect = targetCard.locator(".optional-row select");
  const addOptionalBtn = targetCard.getByRole("button", { name: "Add Optional" });
  if ((await optionalSelect.count()) === 0 || (await addOptionalBtn.count()) === 0) {
    result.warnings.push(`Optional attribute controls unavailable for plugin '${pluginName}'.`);
    return;
  }

  const available = await optionalSelect.first().locator("option").evaluateAll((nodes) => nodes.map((node) => node.value));
  if (!available.includes(field)) {
    result.warnings.push(`Optional field '${field}' not available for plugin '${pluginName}'.`);
    return;
  }

  await optionalSelect.first().selectOption(field);
  await addOptionalBtn.first().click();

  const matchingRow = targetCard.locator(".field-row", { has: targetCard.locator(`label:has-text('${field}')`) }).first();
  if ((await matchingRow.count()) === 0) {
    result.warnings.push(`Added field '${field}' but could not locate editable row.`);
    return;
  }

  const editable = matchingRow.locator("input:not([disabled]), textarea:not([disabled]), select:not([disabled])").first();
  if ((await editable.count()) === 0) {
    result.warnings.push(`Field '${field}' is not editable in UI.`);
    return;
  }

  const tagName = await editable.evaluate((element) => element.tagName.toLowerCase());
  if (tagName === "select") {
    const options = await editable.locator("option").evaluateAll((nodes) => nodes.map((node) => node.value).filter(Boolean));
    if (options.length > 0) {
      await editable.selectOption(String(value || options[0]));
    }
  } else {
    await editable.fill(String(value === undefined || value === null ? "" : value));
  }
}

async function saveFromUi(page, destinationPath) {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Save" }).click(),
  ]);

  const tmpPath = await download.path();
  if (!tmpPath) {
    throw new Error("Playwright did not provide a download path for saved file.");
  }
  await fs.copyFile(tmpPath, destinationPath);
  return destinationPath;
}

function checkSavedOutput(savedJson, latestVersion, config) {
  const issues = [];
  const env = (savedJson && savedJson.config && savedJson.config.env) || {};
  const expectedMetadata = {
    "_metadata.config_version": latestVersion,
  };

  Object.entries(expectedMetadata).forEach(([key, expected]) => {
    const actual = Object.prototype.hasOwnProperty.call(env, key) ? String(env[key]) : "";
    if (String(expected) && actual !== String(expected)) {
      issues.push(`Expected ${key}=${expected}, found '${actual || "<missing>"}'.`);
    }
  });

  if (!Object.prototype.hasOwnProperty.call(env, "_metadata.configuration_date")) {
    issues.push("Expected _metadata.configuration_date to be present.");
  }

  const additional = config.additionalPluginAttribute || {};
  if (additional.pluginName && additional.field) {
    const allPlugins = [];
    const pipeline = (savedJson && savedJson.config && savedJson.config.pipeline) || {};
    ["inputs", "filters", "outputs"].forEach((section) => {
      const list = Array.isArray(pipeline[section]) ? pipeline[section] : [];
      list.forEach((plugin) => allPlugins.push(plugin));
    });

    const matching = allPlugins.find((plugin) => String(plugin && plugin.name || "").toLowerCase() === String(additional.pluginName).toLowerCase());
    if (!matching) {
      issues.push(`Saved output did not include plugin '${additional.pluginName}'.`);
    } else if (!Object.prototype.hasOwnProperty.call(matching, additional.field)) {
      issues.push(`Saved output missing plugin field '${additional.field}' on '${additional.pluginName}'.`);
    }
  }

  const hasPluginComment = (() => {
    const pipeline = (savedJson && savedJson.config && savedJson.config.pipeline) || {};
    return ["inputs", "filters", "outputs"].some((section) => {
      const list = Array.isArray(pipeline[section]) ? pipeline[section] : [];
      return list.some((plugin) => plugin && plugin._meta && Array.isArray(plugin._meta.comment_lines) && plugin._meta.comment_lines.length > 0);
    });
  })();

  if (!hasPluginComment) {
    issues.push("Saved output has no plugin comments in _meta.comment_lines.");
  }

  return issues;
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(payload, null, 2), "utf-8");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = String(args["base-url"] || "http://127.0.0.1:8091/config-service/ui");
  const sourceRoot = path.resolve(String(args["source-root"] || process.cwd()));
  const configFile = path.resolve(String(args["config-file"] || "./dev-tools/playwright-batch-config/default-batch-config.json"));
  const reportFile = path.resolve(String(args["report-file"] || "./dev-tools/playwright-batch-artifacts/execution-report.json"));
  const outputDir = path.resolve(String(args["output-dir"] || "./dev-tools/playwright-batch-artifacts/modified"));
  const discrepancyDir = path.resolve(String(args["discrepancy-dir"] || "./dev-tools/playwright-batch-artifacts/discrepancies"));

  const config = JSON.parse(await fs.readFile(configFile, "utf-8"));
  const yamlFiles = await discoverYamlFiles(sourceRoot, config);

  const report = {
    started_at: new Date().toISOString(),
    base_url: baseUrl,
    source_root: sourceRoot,
    config_file: configFile,
    total_files: yamlFiles.length,
    passed: 0,
    failed: 0,
    with_discrepancies: 0,
    results: [],
  };

  if (yamlFiles.length === 0) {
    report.finished_at = new Date().toISOString();
    await writeJson(reportFile, report);
    console.log(`No YAML files found under ${sourceRoot}`);
    return;
  }

  await fs.mkdir(outputDir, { recursive: true });
  await fs.mkdir(discrepancyDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });

  try {
    for (const yamlFile of yamlFiles) {
      const started = Date.now();
      const relative = path.relative(sourceRoot, yamlFile);
      const result = {
        source_file: yamlFile,
        relative_source_file: relative,
        output_file: "",
        status: "passed",
        plugin_count: 0,
        missing_paths: [],
        warnings: [],
        errors: [],
        duration_ms: 0,
      };

      const context = await browser.newContext({ acceptDownloads: true });
      const page = await context.newPage();

      try {
        await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
        await page.getByRole("heading", { name: "Config Service" }).waitFor({ timeout: 20_000 });
        await page.locator("#plugin-name option").first().waitFor({ timeout: 20_000 });

        await page.getByRole("button", { name: "New Configuration" }).click();
        await page.locator("#open-file").setInputFiles(yamlFile);

        await page.getByRole("button", { name: "Render" }).click();
        await page.locator("#yaml-output").waitFor({ timeout: 20_000 });

        const latestVersion = await uiLatestVersion(page);
        if (!latestVersion) {
          result.warnings.push("Could not determine latest version from UI version selector.");
        }

        await ensurePanelOpenIfCollapsed(page, "#metadata-env-toggle");
        await addMetadataVariable(page, "config_version", latestVersion || "");
        await addMetadataVariable(page, "SCM_config_version", `${path.basename(yamlFile, path.extname(yamlFile))}-rev`);
        await addMetadataVariable(page, "configuration_date", todayIsoDate());

        result.plugin_count = await annotatePlugins(page, path.basename(yamlFile));
        await addAdditionalPluginAttribute(page, config, result);

        await page.getByRole("button", { name: "Render" }).click();
        const renderedText = await page.locator("#yaml-output").textContent();

        const sourceModel = loadYamlFile(yamlFile);
        const renderedModel = safeYamlParse(renderedText || "");
        const sourcePaths = flattenPaths(sourceModel);
        const renderedPaths = flattenPaths(renderedModel);
        result.missing_paths = Array.from(sourcePaths).filter((pathToken) => !renderedPaths.has(pathToken));

        if (result.missing_paths.length > 0) {
          result.status = "discrepancy";
          result.warnings.push(`Rendered output missing ${result.missing_paths.length} source path(s).`);
        }

        const outputBaseName = `${path.basename(yamlFile, path.extname(yamlFile))}${String(config.saveSuffix || "-ui-validated")}.json`;
        const outputPath = path.join(outputDir, outputBaseName);
        await saveFromUi(page, outputPath);
        result.output_file = outputPath;

        const savedRaw = await fs.readFile(outputPath, "utf-8");
        let savedJson = null;
        try {
          savedJson = JSON.parse(savedRaw);
        } catch (err) {
          throw new Error(`Saved output is not JSON: ${err.message}`);
        }

        const outputIssues = checkSavedOutput(savedJson, latestVersion, config);
        if (outputIssues.length > 0) {
          result.status = "failed";
          result.errors.push(...outputIssues);
        }
      } catch (err) {
        result.status = "failed";
        result.errors.push(err && err.message ? err.message : String(err));
      } finally {
        result.duration_ms = Date.now() - started;
        await context.close();
      }

      if (result.status === "passed") {
        report.passed += 1;
      } else if (result.status === "discrepancy") {
        report.with_discrepancies += 1;
        const discrepancyPath = path.join(discrepancyDir, `${path.basename(yamlFile)}.discrepancy.json`);
        await writeJson(discrepancyPath, result);
      } else {
        report.failed += 1;
        const discrepancyPath = path.join(discrepancyDir, `${path.basename(yamlFile)}.failure.json`);
        await writeJson(discrepancyPath, result);
      }

      report.results.push(result);
      console.log(`[${result.status.toUpperCase()}] ${result.relative_source_file}`);
    }
  } finally {
    await browser.close();
  }

  report.finished_at = new Date().toISOString();
  await writeJson(reportFile, report);

  const hasFailures = report.failed > 0 || report.with_discrepancies > 0;
  if (hasFailures) {
    console.log(`Completed with issues. failed=${report.failed}, discrepancies=${report.with_discrepancies}`);
    process.exitCode = 1;
  } else {
    console.log(`Completed successfully. passed=${report.passed}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
