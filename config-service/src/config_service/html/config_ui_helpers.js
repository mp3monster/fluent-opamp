/*
 * Copyright 2026 mp3monster.org
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

(function (global) {
  "use strict";

  function prependConfigHeader(text, configType, version, commentPrefix) {
    var prefix = commentPrefix || "#";
    var header = [
      prefix + " config-service: config_type=" + String(configType || ""),
      prefix + " config-service: version=" + String(version || ""),
    ].join("\n");
    return header + "\n" + String(text || "");
  }

  function versionAtLeast(actual, minimum) {
    var a = String(actual || "").split(".").map(function (part) {
      return Number(part || 0);
    });
    var b = String(minimum || "").split(".").map(function (part) {
      return Number(part || 0);
    });
    var length = Math.max(a.length, b.length);
    for (var index = 0; index < length; index += 1) {
      var left = a[index] || 0;
      var right = b[index] || 0;
      if (left > right) {
        return true;
      }
      if (left < right) {
        return false;
      }
    }
    return true;
  }

  function getEnumOptions(field) {
    if (!field || typeof field !== "object") {
      return [];
    }
    if (Array.isArray(field.called_enum_options)) {
      return field.called_enum_options.slice();
    }
    if (Array.isArray(field.enum_options)) {
      return field.enum_options.slice();
    }
    return [];
  }

  function defaultForField(field) {
    var enumOptions = getEnumOptions(field);
    if (enumOptions.length > 0) {
      if (Object.prototype.hasOwnProperty.call(field, "default") && field.default !== "") {
        return field.default;
      }
      return enumOptions[0];
    }
    if (Object.prototype.hasOwnProperty.call(field, "default")) {
      return field.default;
    }
    var t = String(field.data_type || "string").toLowerCase();
    if (t === "integer" || t === "number" || t === "float") {
      return 0;
    }
    if (t === "boolean") {
      return false;
    }
    if (t === "array" || t === "list") {
      return [];
    }
    if (t === "object" || t === "map") {
      return {};
    }
    return "";
  }

  function normalizeEnumAliasValue(enumOptions, value) {
    var options = Array.isArray(enumOptions) ? enumOptions.map(function (item) { return String(item); }) : [];
    if (options.length === 0) {
      return value;
    }
    var raw = value;
    if (raw === undefined || raw === null) {
      return raw;
    }
    var text = String(raw).trim();
    var lower = text.toLowerCase();
    if (options.indexOf("on") !== -1 && options.indexOf("off") !== -1) {
      if (raw === true || lower === "true" || lower === "1" || lower === "yes" || lower === "on") {
        return "on";
      }
      if (raw === false || lower === "false" || lower === "0" || lower === "no" || lower === "off") {
        return "off";
      }
    }
    return text;
  }

  function parseTextValue(raw, dataType) {
    var t = String(dataType || "string").toLowerCase();
    if (t === "integer") {
      var i = Number(raw);
      return Number.isFinite(i) ? Math.trunc(i) : 0;
    }
    if (t === "number" || t === "float") {
      var n = Number(raw);
      return Number.isFinite(n) ? n : 0;
    }
    if (t === "array" || t === "list" || t === "object" || t === "map") {
      try {
        return raw ? JSON.parse(raw) : t === "array" || t === "list" ? [] : {};
      } catch (_e) {
        return raw;
      }
    }
    return raw;
  }

  function parseServiceValue(raw) {
    var v = String(raw || "").trim();
    if (v === "true") {
      return true;
    }
    if (v === "false") {
      return false;
    }
    if (v !== "" && !Number.isNaN(Number(v))) {
      return Number(v);
    }
    try {
      if ((v.startsWith("{") && v.endsWith("}")) || (v.startsWith("[") && v.endsWith("]"))) {
        return JSON.parse(v);
      }
    } catch (_e) {
      return raw;
    }
    return raw;
  }

  function parseServiceValueByType(raw, dataType) {
    var t = String(dataType || "string").toLowerCase();
    if (t === "enum") {
      return String(raw || "");
    }
    if (t === "boolean") {
      var v = String(raw || "").trim().toLowerCase();
      return v === "true" || v === "1" || v === "yes" || v === "on";
    }
    if (t === "integer") {
      var i = Number(raw);
      return Number.isFinite(i) ? Math.trunc(i) : 0;
    }
    if (t === "number" || t === "float") {
      var f = Number(raw);
      return Number.isFinite(f) ? f : 0;
    }
    return parseServiceValue(raw);
  }

  function fieldInputValue(value, dataType) {
    var t = String(dataType || "string").toLowerCase();
    if (t === "array" || t === "list" || t === "object" || t === "map") {
      try {
        return JSON.stringify(value === undefined ? null : value);
      } catch (_e) {
        return String(value || "");
      }
    }
    if (value === undefined || value === null) {
      return "";
    }
    return String(value);
  }

  function parseFlexibleRouteValue(raw) {
    var text = String(raw || "").trim();
    if (text === "") {
      return "";
    }
    try {
      if (
        (text.startsWith("[") && text.endsWith("]")) ||
        (text.startsWith("{") && text.endsWith("}")) ||
        text === "true" ||
        text === "false" ||
        text === "null"
      ) {
        return JSON.parse(text);
      }
    } catch (_e) {
      return raw;
    }
    if (!Number.isNaN(Number(text)) && text !== "") {
      return Number(text);
    }
    return raw;
  }

  function formatFlexibleRouteValue(value) {
    if (value === undefined || value === null) {
      return value === null ? "null" : "";
    }
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (_e) {
        return String(value);
      }
    }
    return String(value);
  }

  global.ConfigServiceUiHelpers = {
    prependConfigHeader: prependConfigHeader,
    versionAtLeast: versionAtLeast,
    getEnumOptions: getEnumOptions,
    defaultForField: defaultForField,
    normalizeEnumAliasValue: normalizeEnumAliasValue,
    parseTextValue: parseTextValue,
    parseServiceValue: parseServiceValue,
    parseServiceValueByType: parseServiceValueByType,
    fieldInputValue: fieldInputValue,
    parseFlexibleRouteValue: parseFlexibleRouteValue,
    formatFlexibleRouteValue: formatFlexibleRouteValue,
  };
})(window);
