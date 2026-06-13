import { beforeAll, describe, expect, test, vi } from "vitest";
import { loadUiScript } from "./setup/load-ui-script.js";

function createElement(tagName, value) {
  const node = document.createElement(tagName);
  if (value !== undefined) {
    node.value = value;
  }
  return node;
}

describe("ConfigServiceUiEnv", function () {
  beforeAll(function () {
    loadUiScript("config_ui_helpers.js");
    loadUiScript("config_ui_metadata.js");
    loadUiScript("config_ui_env.js");
  });

  test("separates metadata from regular environment variables", function () {
    const state = {
      versions: ["5.0.4"],
      selectedVersion: "5.0.4",
      doc: {
        version: "5.0.4",
        config: {
          env: {
            normal_key: "normal",
            "_metadata.config_version": "5.0.4",
            "_metadata.SCM_config_version": "cfg-001",
          },
        },
      },
    };
    const el = {
      envList: createElement("div"),
      metadataEnvList: createElement("div"),
      metadataEnvKeyInput: createElement("input"),
      metadataEnvKeyOptions: createElement("datalist"),
      metadataEnvValueInput: createElement("input"),
      metadataEnvValueOptions: createElement("datalist"),
    };
    const api = window.ConfigServiceUiEnv.create({
      state: state,
      el: el,
      saveDoc: vi.fn(),
      ensureDoc: function () {},
      isReadOnlyMode: function () { return false; },
      parseServiceValue: window.ConfigServiceUiHelpers.parseServiceValue,
    });

    api.renderEnv();

    const normalKeys = Array.from(el.envList.querySelectorAll("input"))
      .map(function (node) { return node.value; });
    const metadataKeys = Array.from(el.metadataEnvList.querySelectorAll("input"))
      .map(function (node) { return node.value; });

    expect(normalKeys).toContain("normal_key");
    expect(normalKeys).not.toContain("_metadata.config_version");
    expect(metadataKeys).toContain("config_version");
    expect(metadataKeys).toContain("SCM_config_version");
  });

  test("normalizes metadata keys when adding new entries", function () {
    const state = {
      versions: ["5.0.4"],
      selectedVersion: "5.0.4",
      doc: { version: "5.0.4", config: { env: {} } },
    };
    const el = {
      envList: createElement("div"),
      metadataEnvList: createElement("div"),
      metadataEnvKeyInput: createElement("input"),
      metadataEnvKeyOptions: createElement("datalist"),
      metadataEnvValueInput: createElement("input"),
      metadataEnvValueOptions: createElement("datalist"),
      addMetadataEnvField: createElement("button"),
    };
    const api = window.ConfigServiceUiEnv.create({
      state: state,
      el: el,
      saveDoc: vi.fn(),
      ensureDoc: function () {},
      isReadOnlyMode: function () { return false; },
      parseServiceValue: window.ConfigServiceUiHelpers.parseServiceValue,
    });

    api.bindEvents();
    el.metadataEnvKeyInput.value = "_.metadata.custom_label";
    el.metadataEnvValueInput.value = "test-value";
    el.addMetadataEnvField.click();

    expect(state.doc.config.env["_metadata.custom_label"]).toBe("test-value");
    expect(Object.keys(state.doc.config.env)).not.toContain("_.metadata.custom_label");
  });

  test("populates the metadata key datalist with the shared defaults", function () {
    const state = {
      versions: ["5.0.4"],
      selectedVersion: "5.0.4",
      configType: "fluentbit",
      doc: { version: "5.0.4", config: { env: {} } },
    };
    const el = {
      envList: createElement("div"),
      metadataEnvList: createElement("div"),
      metadataEnvKeyInput: createElement("input"),
      metadataEnvKeyOptions: createElement("datalist"),
      metadataEnvValueInput: createElement("input"),
      metadataEnvValueOptions: createElement("datalist"),
    };
    const api = window.ConfigServiceUiEnv.create({
      state: state,
      el: el,
      saveDoc: vi.fn(),
      ensureDoc: function () {},
      isReadOnlyMode: function () { return false; },
      parseServiceValue: window.ConfigServiceUiHelpers.parseServiceValue,
    });

    api.renderEnv();

    const optionValues = Array.from(el.metadataEnvKeyOptions.querySelectorAll("option")).map(function (node) {
      return node.value;
    });
    expect(optionValues).toEqual([
      "config_version",
      "configuration_date",
      "SCM_config_version",
      "config_type",
      "SCM_source_name",
    ]);
  });
});
