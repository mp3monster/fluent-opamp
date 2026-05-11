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
            "_metadata.fluent_bit_version": "5.0.4",
          },
        },
      },
    };
    const el = {
      envList: createElement("div"),
      metadataEnvList: createElement("div"),
      metadataEnvKeyInput: createElement("input"),
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
    expect(normalKeys).not.toContain("_metadata.fluent_bit_version");
    expect(metadataKeys).toContain("fluent_bit_version");
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
});
