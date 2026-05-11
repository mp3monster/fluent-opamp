import { beforeAll, describe, expect, test, vi } from "vitest";
import { loadUiScript } from "./setup/load-ui-script.js";

describe("ConfigServiceUiComments", function () {
  beforeAll(function () {
    loadUiScript("config_ui_comments.js");
  });

  test("stores and clears field comments inside _meta", function () {
    const deps = {
      state: { doc: { config: {} }, commentOpen: {} },
      saveDoc: vi.fn(),
      renderAll: vi.fn(),
      isReadOnlyMode: function () { return false; },
    };
    const api = window.ConfigServiceUiComments.create(deps);
    const target = {};

    api.setFieldCommentText(target, "name", "  first line  \nsecond line\n");
    expect(target._meta.field_comment_lines.name).toEqual(["  first line", "second line"]);
    expect(api.fieldCommentText(target, "name")).toBe("first line\nsecond line");

    api.clearFieldComment(target, "name");
    expect(target._meta).toBeUndefined();
  });

  test("tokenizes legacy annotation paths", function () {
    const deps = {
      state: { doc: { config: {} }, commentOpen: {} },
      saveDoc: vi.fn(),
      renderAll: vi.fn(),
      isReadOnlyMode: function () { return false; },
    };
    const api = window.ConfigServiceUiComments.create(deps);

    expect(api.tokenizeLegacyCommentPath("$.pipeline.inputs[0].name")).toEqual([
      "pipeline",
      "inputs",
      0,
      "name",
    ]);
    expect(api.tokenizeLegacyCommentPath("pipeline.inputs[0].name")).toBeNull();
  });
});
