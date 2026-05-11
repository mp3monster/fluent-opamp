import { beforeAll, describe, expect, test } from "vitest";
import { loadUiScript } from "./setup/load-ui-script.js";

describe("ConfigServiceUiHelpers", function () {
  beforeAll(function () {
    loadUiScript("config_ui_helpers.js");
  });

  test("normalizes on/off aliases for enum-backed values", function () {
    const normalize = window.ConfigServiceUiHelpers.normalizeEnumAliasValue;
    expect(normalize(["on", "off"], true)).toBe("on");
    expect(normalize(["on", "off"], "YES")).toBe("on");
    expect(normalize(["on", "off"], 0)).toBe("off");
  });

  test("keeps non-boolean enum values untouched except trim", function () {
    const normalize = window.ConfigServiceUiHelpers.normalizeEnumAliasValue;
    expect(normalize(["trace", "debug", "info"], " info ")).toBe("info");
    expect(normalize([], " value ")).toBe(" value ");
  });

  test("parses service values by declared type", function () {
    const parseByType = window.ConfigServiceUiHelpers.parseServiceValueByType;
    expect(parseByType("true", "boolean")).toBe(true);
    expect(parseByType("12.9", "integer")).toBe(12);
    expect(parseByType("12.9", "number")).toBe(12.9);
    expect(parseByType("value", "enum")).toBe("value");
  });

  test("parses and formats flexible route values", function () {
    const parseFlexible = window.ConfigServiceUiHelpers.parseFlexibleRouteValue;
    const formatFlexible = window.ConfigServiceUiHelpers.formatFlexibleRouteValue;
    expect(parseFlexible("[1,2]")).toEqual([1, 2]);
    expect(parseFlexible("10")).toBe(10);
    expect(formatFlexible({ a: 1 })).toBe("{\"a\":1}");
    expect(formatFlexible(null)).toBe("null");
  });
});
