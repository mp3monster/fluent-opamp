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

(function () {
  "use strict";

  var API_BASE = "/config-service/api/v1";
  var LAST_FILE_COOKIE = "config_service_last_opened_name";
  var LAST_DOC_STORAGE = "config_service_last_opened_doc";
  var CUSTOM_SERVICE_OPTION = "__custom__";
  var HEADER_PREFIX = "config-service";
  var META_COMMENTS_HELP_URL = "/config-service/ui/docs/meta-comments";
  var SERVICE_OPTIONS = [];
  var lastUiErrorFingerprint = "";
  var lastUiErrorAt = 0;

  var state = {
    versions: [],
    selectedVersion: "",
    catalog: null,
    configType: "fluentbit",
    doc: null,
    collapse: {},
    pluginSection: "inputs",
    pluginName: "",
    catalogLoaded: false,
    currentFileName: "",
    validationStatus: "neutral",
    issueCodeMap: {},
    pendingFocusFieldKey: "",
    serviceCollapsed: false,
    validationCollapsed: false,
    yamlCollapsed: true,
    pluginsPanelCollapsed: false,
    labelsPanelCollapsed: true,
    workersPanelCollapsed: true,
    saveFileHandle: null,
    currentFileDisplay: "",
    lastRenderedSignature: "",
    renderDirty: false,
    readOnly: false,
    commentOpen: {},
  };

  var SERVICE_OPTION_BY_KEY = {};

  function rebuildServiceOptionIndex() {
    SERVICE_OPTION_BY_KEY = {};
    SERVICE_OPTIONS.forEach(function (opt) {
      SERVICE_OPTION_BY_KEY[opt.key] = opt;
    });
  }

  rebuildServiceOptionIndex();

  function applyCssOverrides() {
    var overrides = window.__CONFIG_SERVICE_UI_CSS_OVERRIDES__;
    if (!Array.isArray(overrides) || overrides.length === 0) {
      return;
    }
    overrides.forEach(function (href) {
      if (!href || typeof href !== "string") {
        return;
      }
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.setAttribute("data-config-service-override", "true");
      document.head.appendChild(link);
    });
  }

  function reloadUiWithCacheBust() {
    var url = new URL(window.location.href);
    url.searchParams.set("_ui_reload_ts", String(Date.now()));
    window.location.assign(url.toString());
  }

  var el = {
    openFile: document.getElementById("open-file"),
    openFileDisplay: document.getElementById("open-file-display"),
    browseFile: document.getElementById("browse-file"),
    saveConfig: document.getElementById("save-config"),
    saveAsConfig: document.getElementById("save-as-config"),
    newConfig: document.getElementById("new-config"),
    reloadUi: document.getElementById("reload-ui"),
    versionSelect: document.getElementById("version-select"),
    configTypeSelect: document.getElementById("config-type-select"),
    pluginSection: document.getElementById("plugin-section"),
    pluginName: document.getElementById("plugin-name"),
    pluginHelpToggle: document.getElementById("plugin-help-toggle"),
    addPlugin: document.getElementById("add-plugin"),
    pluginList: document.getElementById("plugin-list"),
    pluginsToggle: document.getElementById("plugins-toggle"),
    pluginsBody: document.getElementById("plugins-body"),
    labelsPanel: document.getElementById("labels-panel"),
    labelsToggle: document.getElementById("labels-toggle"),
    labelsBody: document.getElementById("labels-body"),
    labelList: document.getElementById("label-list"),
    addLabel: document.getElementById("add-label"),
    workersPanel: document.getElementById("workers-panel"),
    workersToggle: document.getElementById("workers-toggle"),
    workersBody: document.getElementById("workers-body"),
    workerList: document.getElementById("worker-list"),
    addWorker: document.getElementById("add-worker"),
    serviceList: document.getElementById("service-list"),
    serviceOption: document.getElementById("service-option"),
    serviceCustomKey: document.getElementById("service-custom-key"),
    serviceValue: document.getElementById("service-value"),
    serviceHelpToggle: document.getElementById("service-help-toggle"),
    addServiceField: document.getElementById("add-service-field"),
    serviceOptionMeta: document.getElementById("service-option-meta"),
    validateBtn: document.getElementById("validate-btn"),
    renderBtn: document.getElementById("render-btn"),
    statusPanel: document.getElementById("status-panel"),
    statusTime: document.getElementById("status-time"),
    statusMessage: document.getElementById("status-message"),
    validationHeader: document.getElementById("validation-header"),
    validationCard: document.getElementById("validation-card"),
    validationToggle: document.getElementById("validation-toggle"),
    validationBody: document.getElementById("validation-body"),
    validationSummary: document.getElementById("validation-summary"),
    validationIssues: document.getElementById("validation-issues"),
    yamlToggle: document.getElementById("yaml-toggle"),
    yamlBody: document.getElementById("yaml-body"),
    yamlOutput: document.getElementById("yaml-output"),
    renderCard: document.getElementById("render-card"),
  };

  function fetchJson(url, options) {
    return fetch(url, options || {}).then(function (resp) {
      return resp.text().then(function (text) {
        var data = {};
        try {
          data = text ? JSON.parse(text) : {};
        } catch (_e) {
          data = { error: text };
        }
        if (!resp.ok) {
          var err = new Error(
            data.error ||
            (Array.isArray(data.errors) && data.errors.length > 0 && data.errors[0].message) ||
            JSON.stringify(data)
          );
          err.payload = data;
          err.status = resp.status;
          throw err;
        }
        return data;
      });
    });
  }

  function reportUiError(details) {
    var payload = details && typeof details === "object" ? details : {};
    var fingerprint = JSON.stringify({
      kind: payload.kind || "",
      message: payload.message || "",
      source: payload.source || "",
      path: payload.path || "",
      line: payload.line || "",
      column: payload.column || "",
    });
    var now = Date.now();
    if (fingerprint === lastUiErrorFingerprint && now - lastUiErrorAt < 4000) {
      return;
    }
    lastUiErrorFingerprint = fingerprint;
    lastUiErrorAt = now;
    fetch(API_BASE + "/client-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: String(payload.kind || "runtime_error"),
        message: String(payload.message || "Unknown UI error"),
        source: String(payload.source || "browser"),
        path: String(payload.path || window.location.href || ""),
        stack: payload.stack ? String(payload.stack) : "",
        line: payload.line === undefined ? null : payload.line,
        column: payload.column === undefined ? null : payload.column,
      }),
      keepalive: true,
    }).catch(function () {
      // Avoid error-reporting loops when the backend is unavailable.
    });
  }

  function installGlobalUiErrorHandlers() {
    window.addEventListener("error", function (event) {
      var error = event && event.error;
      reportUiError({
        kind: "window_error",
        message: error && error.message ? error.message : String((event && event.message) || "Unhandled UI error"),
        source: event && event.filename ? event.filename : "browser",
        path: window.location.href,
        stack: error && error.stack ? error.stack : "",
        line: event && event.lineno ? event.lineno : null,
        column: event && event.colno ? event.colno : null,
      });
    });

    window.addEventListener("unhandledrejection", function (event) {
      var reason = event ? event.reason : null;
      var message = "Unhandled promise rejection";
      var stack = "";
      if (reason && typeof reason === "object") {
        message = String(reason.message || message);
        stack = reason.stack ? String(reason.stack) : "";
      } else if (reason !== undefined && reason !== null) {
        message = String(reason);
      }
      reportUiError({
        kind: "unhandledrejection",
        message: message,
        source: "browser",
        path: window.location.href,
        stack: stack,
      });
    });
  }

  function setCookie(name, value) {
    var expires = new Date();
    expires.setDate(expires.getDate() + 30);
    document.cookie =
      name +
      "=" +
      encodeURIComponent(value) +
      "; expires=" +
      expires.toUTCString() +
      "; path=/; SameSite=Lax";
  }

  function getCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie.split(";");
    for (var i = 0; i < parts.length; i += 1) {
      var part = parts[i].trim();
      if (part.indexOf(prefix) === 0) {
        return decodeURIComponent(part.substring(prefix.length));
      }
    }
    return null;
  }

  function clearCookie(name) {
    document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";
  }

  function emptyDoc(version, configType) {
    return {
      version: version,
      configType: configType || "fluentbit",
      config: {
        service: {},
        pipeline: { inputs: [], filters: [], outputs: [] },
        labels: [],
        workers: [],
        includes: [],
      },
      annotations: {},
    };
  }

  function compareVersionStrings(left, right) {
    var a = String(left || "").split(".").map(function (part) { return Number(part) || 0; });
    var b = String(right || "").split(".").map(function (part) { return Number(part) || 0; });
    var length = Math.max(a.length, b.length);
    for (var index = 0; index < length; index += 1) {
      var diff = (a[index] || 0) - (b[index] || 0);
      if (diff !== 0) {
        return diff;
      }
    }
    return 0;
  }

  function resolvePreferredVersion(versions, preferredVersion, fallbackDefault) {
    var candidates = Array.isArray(versions) ? versions.slice() : [];
    if (candidates.length === 0) {
      return "";
    }
    candidates.sort(compareVersionStrings);
    if (preferredVersion) {
      if (candidates.indexOf(preferredVersion) !== -1) {
        return preferredVersion;
      }
      for (var index = 0; index < candidates.length; index += 1) {
        if (compareVersionStrings(candidates[index], preferredVersion) > 0) {
          return candidates[index];
        }
      }
      return candidates[candidates.length - 1];
    }
    if (fallbackDefault && candidates.indexOf(fallbackDefault) !== -1) {
      return fallbackDefault;
    }
    return candidates[0];
  }

  function clearOpenFileSelection() {
    if (el.openFile) {
      el.openFile.value = "";
    }
    state.currentFileDisplay = "";
    if (el.openFileDisplay) {
      el.openFileDisplay.value = "";
    }
  }

  function isReadOnlyMode() {
    return Boolean(state.readOnly);
  }

  function setOpenFileDisplay(value) {
    state.currentFileDisplay = String(value || "").trim();
    if (el.openFileDisplay) {
      el.openFileDisplay.value = state.currentFileDisplay;
    }
  }

  function currentRenderSignature() {
    if (!state.doc) {
      return "";
    }
    return JSON.stringify({
      configType: state.configType,
      version: state.doc.version || state.selectedVersion,
      config: state.doc.config,
    });
  }

  function updateRenderedDirtyState() {
    if (el.renderCard) {
      el.renderCard.classList.toggle("is-stale", Boolean(state.renderDirty && el.yamlOutput.textContent));
    }
    if (el.yamlOutput) {
      el.yamlOutput.style.color = state.renderDirty ? "#ffd24d" : "#e5ebff";
    }
  }

  function updateReadOnlyState() {
    var readOnly = isReadOnlyMode();
    el.newConfig.disabled = readOnly;
    el.saveConfig.disabled = readOnly;
    el.saveAsConfig.disabled = readOnly;
    el.configTypeSelect.disabled = readOnly || hasConfiguredContent();
    el.versionSelect.disabled = readOnly || !Array.isArray(state.versions) || state.versions.length === 0;
    el.addServiceField.disabled = readOnly;
    el.serviceOption.disabled = readOnly;
    el.serviceCustomKey.disabled = readOnly;
    el.serviceValue.disabled = readOnly;
    el.addPlugin.disabled = readOnly || !(state.catalog && el.pluginName && el.pluginName.value);
    el.pluginSection.disabled = readOnly;
    el.pluginName.disabled = readOnly;
    el.addLabel.disabled = readOnly;
    el.addWorker.disabled = readOnly;
    Array.prototype.forEach.call(
      document.querySelectorAll(
        ".plugin-card input, .plugin-card select, .plugin-card textarea, " +
          ".nested-panel input, .nested-panel select, .nested-panel textarea, " +
          ".plugin-card button, .nested-panel button, .comment-editor textarea"
      ),
      function (node) {
        if (!node || !node.id) {
          // continue
        }
        var allowAction = node.id === "validation-toggle" ||
          node.id === "yaml-toggle" ||
          node.id === "validate-btn" ||
          node.id === "render-btn" ||
          node.id === "reload-ui";
        if (allowAction) {
          return;
        }
        if (node.classList && (node.classList.contains("icon-help") || node.textContent === "Collapse" || node.textContent === "Expand")) {
          node.disabled = false;
          return;
        }
        node.disabled = readOnly;
      }
    );
  }

  function parseConfigHeader(text) {
    var meta = {
      configType: "",
      version: "",
      body: String(text || ""),
    };
    var lines = meta.body.replace(/\r\n/g, "\n").split("\n");
    var bodyStart = 0;
    for (var index = 0; index < lines.length; index += 1) {
      var line = lines[index];
      var trimmed = line.trim();
      var match = /^(?:\/\/|#)\s*config-service:\s*(config_type|version)\s*=\s*(.+?)\s*$/.exec(trimmed);
      if (match) {
        if (match[1] === "config_type") {
          meta.configType = match[2].trim();
        } else if (match[1] === "version") {
          meta.version = match[2].trim();
        }
        bodyStart = index + 1;
        continue;
      }
      if (!trimmed) {
        bodyStart = index + 1;
        continue;
      }
      break;
    }
    meta.body = lines.slice(bodyStart).join("\n");
    return meta;
  }

  function prependConfigHeader(text, configType, version, commentPrefix) {
    var prefix = commentPrefix || "#";
    var header = [
      prefix + " " + HEADER_PREFIX + ": config_type=" + String(configType || ""),
      prefix + " " + HEADER_PREFIX + ": version=" + String(version || ""),
    ].join("\n");
    return header + "\n" + String(text || "");
  }

  function pluginGroups() {
    if (!state.catalog || !state.catalog.plugins) {
      return { inputs: {}, filters: {}, outputs: {} };
    }
    return state.catalog.plugins;
  }

  function isFluentdMode() {
    return state.configType === "fluentd";
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

  function replaceServiceValueControl(tagName) {
    var current = el.serviceValue;
    if (current && current.tagName && current.tagName.toLowerCase() === tagName.toLowerCase()) {
      return current;
    }
    var replacement = document.createElement(tagName);
    replacement.id = "service-value";
    replacement.className = current.className || "";
    replacement.placeholder = current.placeholder || "";
    replacement.value = current.value || "";
    current.parentNode.replaceChild(replacement, current);
    el.serviceValue = replacement;
    return replacement;
  }

  function ensureDoc() {
    if (!state.doc) {
      state.doc = emptyDoc(state.selectedVersion, state.configType);
    }
    if (!state.doc.config || typeof state.doc.config !== "object") {
      state.doc.config = {};
    }
    if (state.doc.pipeline && (!state.doc.config.pipeline || typeof state.doc.config.pipeline !== "object")) {
      state.doc.config.pipeline = state.doc.pipeline;
    }
    if (
      !state.doc.config.pipeline &&
      (
        Array.isArray(state.doc.config.inputs) ||
        Array.isArray(state.doc.config.filters) ||
        Array.isArray(state.doc.config.outputs)
      )
    ) {
      state.doc.config.pipeline = {
        inputs: Array.isArray(state.doc.config.inputs) ? state.doc.config.inputs : [],
        filters: Array.isArray(state.doc.config.filters) ? state.doc.config.filters : [],
        outputs: Array.isArray(state.doc.config.outputs) ? state.doc.config.outputs : [],
      };
      delete state.doc.config.inputs;
      delete state.doc.config.filters;
      delete state.doc.config.outputs;
    }
    if (
      state.doc.config.plugins &&
      typeof state.doc.config.plugins === "object" &&
      !state.doc.config.pipeline
    ) {
      state.doc.config.pipeline = {
        inputs: Array.isArray(state.doc.config.plugins.inputs) ? state.doc.config.plugins.inputs : [],
        filters: Array.isArray(state.doc.config.plugins.filters) ? state.doc.config.plugins.filters : [],
        outputs: Array.isArray(state.doc.config.plugins.outputs) ? state.doc.config.plugins.outputs : [],
      };
    }
    if (!state.doc.annotations || typeof state.doc.annotations !== "object") {
      state.doc.annotations = {};
    }
    if (!state.doc.config.service || typeof state.doc.config.service !== "object") {
      state.doc.config.service = {};
    }
    if (!state.doc.config.pipeline || typeof state.doc.config.pipeline !== "object") {
      state.doc.config.pipeline = {};
    }
    if (!Array.isArray(state.doc.config.labels)) {
      state.doc.config.labels = [];
    }
    if (!Array.isArray(state.doc.config.workers)) {
      state.doc.config.workers = [];
    }
    if (!Array.isArray(state.doc.config.includes)) {
      state.doc.config.includes = [];
    }
    ["inputs", "filters", "outputs"].forEach(function (section) {
      if (!Array.isArray(state.doc.config.pipeline[section])) {
        state.doc.config.pipeline[section] = [];
      }
    });
    migrateLegacyAnnotationsToMeta();
  }

  function ensureMetaBlock(target) {
    if (!target || typeof target !== "object" || Array.isArray(target)) {
      return null;
    }
    if (!target._meta || typeof target._meta !== "object" || Array.isArray(target._meta)) {
      target._meta = {};
    }
    return target._meta;
  }

  function ensureFieldCommentMap(target) {
    var meta = ensureMetaBlock(target);
    if (!meta) {
      return null;
    }
    if (!meta.field_comment_lines || typeof meta.field_comment_lines !== "object" || Array.isArray(meta.field_comment_lines)) {
      meta.field_comment_lines = {};
    }
    return meta.field_comment_lines;
  }

  function commentLinesToText(lines) {
    if (!Array.isArray(lines)) {
      return "";
    }
    return lines
      .filter(function (line) {
        return typeof line === "string";
      })
      .join("\n")
      .trim();
  }

  function textToCommentLines(value) {
    var text = String(value || "").replace(/\r\n/g, "\n");
    var parts = text.split("\n");
    while (parts.length > 0 && parts[0].trim() === "") {
      parts.shift();
    }
    while (parts.length > 0 && parts[parts.length - 1].trim() === "") {
      parts.pop();
    }
    return parts.map(function (line) {
      return line.trimEnd();
    });
  }

  function objectCommentText(target) {
    var meta = ensureMetaBlock(target);
    if (!meta) {
      return "";
    }
    return commentLinesToText(meta.comment_lines);
  }

  function setObjectCommentText(target, value) {
    var meta = ensureMetaBlock(target);
    if (!meta) {
      return;
    }
    var lines = textToCommentLines(value);
    if (lines.length === 0) {
      delete meta.comment_lines;
      if (!meta.field_comment_lines || Object.keys(meta.field_comment_lines).length === 0) {
        delete target._meta;
      }
    } else {
      meta.comment_lines = lines;
    }
    saveDoc();
  }

  function fieldCommentText(target, fieldName) {
    var meta = ensureMetaBlock(target);
    if (!meta || !meta.field_comment_lines) {
      return "";
    }
    return commentLinesToText(meta.field_comment_lines[fieldName]);
  }

  function setFieldCommentText(target, fieldName, value) {
    var fieldMap = ensureFieldCommentMap(target);
    if (!fieldMap) {
      return;
    }
    var lines = textToCommentLines(value);
    if (lines.length === 0) {
      delete fieldMap[fieldName];
      if (Object.keys(fieldMap).length === 0) {
        delete target._meta.field_comment_lines;
      }
      if (target._meta && !target._meta.comment_lines && !target._meta.field_comment_lines) {
        delete target._meta;
      }
    } else {
      fieldMap[fieldName] = lines;
    }
    saveDoc();
  }

  function renameFieldComment(target, oldFieldName, newFieldName) {
    var meta = ensureMetaBlock(target);
    if (!meta || !meta.field_comment_lines || oldFieldName === newFieldName) {
      return;
    }
    if (Object.prototype.hasOwnProperty.call(meta.field_comment_lines, oldFieldName)) {
      meta.field_comment_lines[newFieldName] = meta.field_comment_lines[oldFieldName];
      delete meta.field_comment_lines[oldFieldName];
    }
  }

  function clearFieldComment(target, fieldName) {
    var meta = ensureMetaBlock(target);
    if (!meta || !meta.field_comment_lines) {
      return;
    }
    delete meta.field_comment_lines[fieldName];
    if (Object.keys(meta.field_comment_lines).length === 0) {
      delete meta.field_comment_lines;
    }
    if (!meta.comment_lines && !meta.field_comment_lines) {
      delete target._meta;
    }
  }

  function tokenizeLegacyCommentPath(path) {
    if (typeof path !== "string" || path.charAt(0) !== "$") {
      return null;
    }
    var tokens = [];
    var cursor = 1;
    while (cursor < path.length) {
      var char = path.charAt(cursor);
      if (char === ".") {
        cursor += 1;
        var nextDot = path.indexOf(".", cursor);
        var nextBracket = path.indexOf("[", cursor);
        var end = path.length;
        if (nextDot !== -1) {
          end = Math.min(end, nextDot);
        }
        if (nextBracket !== -1) {
          end = Math.min(end, nextBracket);
        }
        tokens.push(path.slice(cursor, end));
        cursor = end;
        continue;
      }
      if (char === "[") {
        var close = path.indexOf("]", cursor);
        if (close === -1) {
          return null;
        }
        tokens.push(Number(path.slice(cursor + 1, close)));
        cursor = close + 1;
        continue;
      }
      return null;
    }
    return tokens;
  }

  function migrateLegacyAnnotationsToMeta() {
    if (!state.doc || !state.doc.annotations || Object.keys(state.doc.annotations).length === 0) {
      return;
    }
    var annotations = state.doc.annotations;
    Object.keys(annotations).forEach(function (path) {
      var tokens = tokenizeLegacyCommentPath(path);
      if (!tokens || tokens.length === 0) {
        return;
      }
      var cursor = state.doc.config;
      var parent = null;
      var lastToken = null;
      for (var index = 0; index < tokens.length; index += 1) {
        lastToken = tokens[index];
        parent = cursor;
        if (parent === undefined || parent === null) {
          return;
        }
        cursor = parent[lastToken];
      }
      var text = String(annotations[path] || "");
      if (cursor && typeof cursor === "object" && !Array.isArray(cursor)) {
        setObjectCommentText(cursor, text);
        return;
      }
      if (parent && typeof parent === "object" && typeof lastToken === "string") {
        setFieldCommentText(parent, lastToken, text);
      }
    });
    state.doc.annotations = {};
  }

  function createCommentEditor(target, labelText, fieldName) {
    return createCommentEditorPanel(target, labelText, fieldName, "");
  }

  function hasCommentText(target, fieldName) {
    var text = fieldName ? fieldCommentText(target, fieldName) : objectCommentText(target);
    return Boolean(String(text || "").trim());
  }

  function isCommentEditorOpen(toggleKey, target, fieldName) {
    if (toggleKey && Object.prototype.hasOwnProperty.call(state.commentOpen, toggleKey)) {
      return Boolean(state.commentOpen[toggleKey]);
    }
    return hasCommentText(target, fieldName);
  }

  function setCommentEditorOpen(toggleKey, isOpen) {
    if (!toggleKey) {
      return;
    }
    state.commentOpen[toggleKey] = Boolean(isOpen);
  }

  function createMetaHelpButton() {
    var helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.textContent = "?";
    helpBtn.className = "icon-help";
    helpBtn.title = "Open help for _meta comments and field_comment_lines.";
    helpBtn.setAttribute("aria-label", "Open help for _meta comments");
    helpBtn.addEventListener("click", function () {
      window.open(META_COMMENTS_HELP_URL, "_blank", "noopener,noreferrer");
    });
    return helpBtn;
  }

  function createCommentToggleButton(toggleKey, target, fieldName, labelText) {
    var btn = document.createElement("button");
    var isOpen = isCommentEditorOpen(toggleKey, target, fieldName);
    var hasContent = hasCommentText(target, fieldName);
    btn.type = "button";
    btn.textContent = hasContent ? "📝" : "🗒";
    btn.className = "icon-button icon-note";
    if (isOpen) {
      btn.classList.add("is-active");
    }
    if (hasContent) {
      btn.classList.add("has-comment");
    }
    btn.title = (isOpen ? "Hide " : "Open ") + (labelText || "comment editor");
    btn.setAttribute("aria-label", (isOpen ? "Hide " : "Open ") + (labelText || "comment editor"));
    btn.addEventListener("click", function () {
      setCommentEditorOpen(toggleKey, !isOpen);
      renderAll();
    });
    return btn;
  }

  function createCommentEditorPanel(target, labelText, fieldName, toggleKey) {
    var wrap = document.createElement("div");
    wrap.className = "comment-editor";
    if (!isCommentEditorOpen(toggleKey, target, fieldName)) {
      wrap.classList.add("hidden");
    }

    var label = document.createElement("label");
    label.className = "comment-label";
    label.textContent = labelText || "Comment";

    var input = document.createElement("textarea");
    input.className = "comment-input";
    input.rows = 2;
    input.placeholder = "Optional comment";
    input.value = fieldName ? fieldCommentText(target, fieldName) : objectCommentText(target);
    input.disabled = isReadOnlyMode();
    input.addEventListener("change", function () {
      if (fieldName) {
        setFieldCommentText(target, fieldName, input.value);
        setCommentEditorOpen(toggleKey, true);
        saveDoc();
        return;
      }
      setObjectCommentText(target, input.value);
      setCommentEditorOpen(toggleKey, true);
      saveDoc();
    });

    label.appendChild(input);
    wrap.appendChild(label);
    return wrap;
  }

  function saveDoc() {
    if (!state.doc) {
      return;
    }
    localStorage.setItem(LAST_DOC_STORAGE, JSON.stringify(state.doc));
    markValidationDirtyOnEdit();
    if (state.lastRenderedSignature && state.lastRenderedSignature !== currentRenderSignature()) {
      state.renderDirty = true;
      updateRenderedDirtyState();
    }
    updateConfigTypeDisabledState();
  }

  function markValidationDirtyOnEdit() {
    if (state.validationStatus !== "valid") {
      return;
    }
    state.validationStatus = "neutral";
    renderValidationState(null);
  }

  function renderValidationState(result) {
    var errors = (result && Array.isArray(result.errors)) ? result.errors.slice() : [];
    errors.sort(function (a, b) {
      return Number((a && a.order) || 0) - Number((b && b.order) || 0);
    });
    var hasErrors = errors.length > 0 || (result && result.ok === false);
    var isValid = Boolean(result && result.ok === true && errors.length === 0);

    el.validationHeader.classList.remove("is-valid", "has-errors");
    el.validationSummary.classList.remove("is-valid", "has-errors");
    el.validationIssues.innerHTML = "";

    if (isValid) {
      state.validationStatus = "valid";
      el.validationHeader.classList.add("is-valid");
      el.validationSummary.classList.add("is-valid");
      el.validationSummary.textContent = "Configuration is valid.";
      state.validationCollapsed = false;
    } else if (hasErrors) {
      state.validationStatus = "error";
      el.validationHeader.classList.add("has-errors");
      el.validationSummary.classList.add("has-errors");
      el.validationSummary.textContent = errors.length > 0
        ? "Validation found " + errors.length + " error" + (errors.length === 1 ? "" : "s") + "."
        : "Validation failed.";
      state.validationCollapsed = false;

      errors.forEach(function (issue, idx) {
        var item = document.createElement("li");
        var code = String((issue && issue.code) || "unknown_issue");
        var mapping = state.issueCodeMap[code] || state.issueCodeMap.unknown_issue || null;
        var friendlyLabel = mapping && mapping.label ? mapping.label : code;
        var messageText = issue && issue.message
          ? issue.message
          : "Validation error #" + (idx + 1);
        var detailBits = [];
        if (issue && issue.path) {
          detailBits.push("Path: " + issue.path);
        }
        if (issue && issue.severity) {
          detailBits.push("Severity: " + issue.severity);
        }
        if (issue && issue.source) {
          detailBits.push("Source: " + issue.source);
        }
        item.textContent =
          friendlyLabel +
          ": " +
          messageText +
          (detailBits.length > 0 ? " (" + detailBits.join(" | ") + ")" : "");

        el.validationIssues.appendChild(item);
      });
    } else {
      state.validationStatus = "neutral";
      el.validationSummary.textContent = "Run validation to inspect the current configuration.";
      state.validationCollapsed = false;
    }

    updateResultPanels();
  }

  function formatStatusTimestamp() {
    return new Date().toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "medium",
    });
  }

  function setValidationText(text) {
    renderValidationState({
      ok: false,
      errors: [
        {
          message: String(text || "Validation failed."),
          path: "$",
          code: "ui_message",
          severity: "error",
          source: "ui",
        },
      ],
    });
  }

  function setStatusMessage(text) {
    var message = String(text || "").trim();
    if (!message) {
      el.statusTime.textContent = "";
      el.statusMessage.textContent = "";
      el.statusPanel.classList.add("hidden");
      return;
    }
    el.statusTime.textContent = formatStatusTimestamp();
    el.statusMessage.textContent = message;
    el.statusPanel.classList.remove("hidden");
  }

  function setYamlText(text, markFresh) {
    el.yamlOutput.textContent = text || "";
    if (markFresh === true) {
      state.lastRenderedSignature = currentRenderSignature();
      state.renderDirty = false;
    }
    updateRenderedDirtyState();
    updateResultPanels();
  }

  function updateResultPanels() {
    el.validationBody.classList.toggle("is-collapsed", state.validationCollapsed);
    el.validationToggle.textContent = state.validationCollapsed ? "Open" : "Collapse";
    el.yamlBody.classList.toggle("is-collapsed", state.yamlCollapsed);
    el.yamlToggle.textContent = state.yamlCollapsed ? "Open" : "Collapse";
  }

  function updateSectionPanels() {
    if (el.pluginsBody && el.pluginsToggle) {
      el.pluginsBody.classList.toggle("is-collapsed", state.pluginsPanelCollapsed);
      el.pluginsToggle.textContent = state.pluginsPanelCollapsed ? "Open" : "Collapse";
    }
    if (el.labelsBody && el.labelsToggle) {
      el.labelsBody.classList.toggle("is-collapsed", state.labelsPanelCollapsed);
      el.labelsToggle.textContent = state.labelsPanelCollapsed ? "Open" : "Collapse";
    }
    if (el.workersBody && el.workersToggle) {
      el.workersBody.classList.toggle("is-collapsed", state.workersPanelCollapsed);
      el.workersToggle.textContent = state.workersPanelCollapsed ? "Open" : "Collapse";
    }
  }

  function repopulatePluginNameSelect() {
    var groups = pluginGroups();
    var map = groups[state.pluginSection] || {};
    var names = Object.keys(map).sort();
    el.pluginName.innerHTML = "";
    names.forEach(function (name) {
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      el.pluginName.appendChild(opt);
    });
    state.pluginName = names[0] || "";
    el.pluginName.value = state.pluginName;
    updatePluginHelpState();
    updateAddPluginState();
  }

  function repopulateVersions() {
    el.versionSelect.innerHTML = "";
    if (!Array.isArray(state.versions) || state.versions.length === 0) {
      var emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "No versions available";
      el.versionSelect.appendChild(emptyOption);
      el.versionSelect.value = "";
      el.versionSelect.disabled = true;
      return;
    }
    state.versions.forEach(function (v) {
      var opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      el.versionSelect.appendChild(opt);
    });
    el.versionSelect.disabled = isReadOnlyMode() ? true : false;
    el.versionSelect.value = state.selectedVersion;
  }

  function loadVersionsForType(configType, preferredVersion) {
    return fetchJson(API_BASE + "/versions?config_type=" + encodeURIComponent(configType)).then(function (data) {
      var versions = Array.isArray(data.versions) ? data.versions.slice() : [];
      state.versions = versions;
      var currentPreferred = preferredVersion || state.selectedVersion || "";
      state.selectedVersion = resolvePreferredVersion(versions, currentPreferred, data.default || "");

      if (state.doc) {
        state.doc.version = state.selectedVersion;
        state.doc.configType = configType;
      }

      repopulateVersions();
      updateFluentdSectionVisibility();
      return {
        versions: versions,
        defaultVersion: data.default || "",
      };
    });
  }

  function selectedServiceOption() {
    var selectedKey = String(el.serviceOption.value || "");
    return SERVICE_OPTION_BY_KEY[selectedKey] || null;
  }

  function repopulateServiceOptionSelect() {
    el.serviceOption.innerHTML = "";
    SERVICE_OPTIONS.forEach(function (opt) {
      var option = document.createElement("option");
      option.value = opt.key;
      option.textContent = opt.key;
      el.serviceOption.appendChild(option);
    });
    var customOpt = document.createElement("option");
    customOpt.value = CUSTOM_SERVICE_OPTION;
    customOpt.textContent = "custom...";
    el.serviceOption.appendChild(customOpt);
    el.serviceOption.value = SERVICE_OPTIONS[0] ? SERVICE_OPTIONS[0].key : CUSTOM_SERVICE_OPTION;
    updateServiceOptionUI();
  }

  function updateServiceOptionUI() {
    var opt = selectedServiceOption();
    var isCustom = el.serviceOption.value === CUSTOM_SERVICE_OPTION;
    if (el.serviceCustomKey && el.serviceCustomKey.parentElement) {
      el.serviceCustomKey.parentElement.classList.toggle("hidden", !isCustom);
    }
    if (opt) {
      var enumOptions = getEnumOptions(opt);
      if (String(opt.data_type || "").toLowerCase() === "enum" && enumOptions.length > 0) {
        var select = replaceServiceValueControl("select");
        select.innerHTML = "";
        enumOptions.forEach(function (value) {
          var option = document.createElement("option");
          option.value = String(value);
          option.textContent = String(value);
          select.appendChild(option);
        });
        select.value = String(
          normalizeEnumAliasValue(
            enumOptions,
            Object.prototype.hasOwnProperty.call(opt, "default") && opt.default !== ""
              ? opt.default
              : enumOptions[0]
          )
        );
        select.disabled = isReadOnlyMode();
      } else if (String(opt.data_type || "").toLowerCase() === "code") {
        var codeInput = replaceServiceValueControl("textarea");
        codeInput.placeholder = String(opt.default || "");
        codeInput.value = "";
        prepareCodeTextarea(codeInput);
        codeInput.disabled = isReadOnlyMode();
      } else {
        var input = replaceServiceValueControl("input");
        input.type = "text";
        input.placeholder = String(opt.default);
        input.value = "";
        input.disabled = isReadOnlyMode();
      }
      el.serviceOptionMeta.innerHTML = opt.reference
        ? opt.description +
          " " +
          '<a href=\"' +
          opt.reference +
          '\" target=\"_blank\" rel=\"noreferrer\">reference</a>'
        : opt.description;
      el.serviceHelpToggle.disabled = false;
      el.serviceHelpToggle.title = opt.key + ": " + opt.description;
    } else {
      var customInput = replaceServiceValueControl("input");
      customInput.type = "text";
      customInput.placeholder = "value";
      customInput.value = "";
      customInput.disabled = isReadOnlyMode();
      el.serviceOptionMeta.textContent = "Define a custom service key and value.";
      el.serviceHelpToggle.disabled = isCustom;
      el.serviceHelpToggle.title = isCustom
        ? "Custom keys do not have linked Fluent Bit documentation."
        : "Select a service option to view help.";
    }
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

  function maxCodeEditorHeight() {
    var viewport = window.innerHeight || 800;
    return Math.max(180, viewport - 260);
  }

  function resizeCodeTextarea(textarea) {
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = String(Math.max(140, Math.min(textarea.scrollHeight, maxCodeEditorHeight()))) + "px";
  }

  function prepareCodeTextarea(textarea) {
    if (!textarea) {
      return;
    }
    textarea.classList.add("code-input");
    textarea.setAttribute("spellcheck", "false");
    textarea.setAttribute("wrap", "off");
    textarea.style.maxHeight = String(maxCodeEditorHeight()) + "px";
    resizeCodeTextarea(textarea);
    if (textarea.dataset.codeResizeBound !== "true") {
      textarea.addEventListener("input", function () {
        resizeCodeTextarea(textarea);
      });
      textarea.dataset.codeResizeBound = "true";
    }
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

  function flattenPlugins() {
    ensureDoc();
    var out = [];
    ["inputs", "filters", "outputs"].forEach(function (section) {
      state.doc.config.pipeline[section].forEach(function (instance, index) {
        out.push({ section: section, index: index, instance: instance });
      });
    });
    return out;
  }

  function flattenPipeline(pipeline, prefix) {
    var out = [];
    if (!pipeline || typeof pipeline !== "object") {
      return out;
    }
    ["inputs", "filters", "outputs"].forEach(function (section) {
      var list = Array.isArray(pipeline[section]) ? pipeline[section] : [];
      list.forEach(function (instance, index) {
        out.push({
          section: section,
          index: index,
          instance: instance,
          prefix: prefix || "main",
          pipeline: pipeline,
        });
      });
    });
    return out;
  }

  function hasConfiguredContent() {
    ensureDoc();
    var serviceCount = Object.keys(state.doc.config.service || {}).length;
    var pluginCount = flattenPlugins().length;
    var labelCount = Array.isArray(state.doc.config.labels) ? state.doc.config.labels.length : 0;
    var workerCount = Array.isArray(state.doc.config.workers) ? state.doc.config.workers.length : 0;
    return serviceCount > 0 || pluginCount > 0 || labelCount > 0 || workerCount > 0;
  }

  function updateConfigTypeDisabledState() {
    el.configTypeSelect.disabled = isReadOnlyMode() || hasConfiguredContent();
  }

  function defaultSaveFileName() {
    var base = state.currentFileName || getCookie(LAST_FILE_COOKIE) || "";
    if (base && !/^new-\d+$/i.test(base)) {
      if (state.configType === "fluentd") {
        return /\.conf$/i.test(base) ? base : base.replace(/\.[^.]+$/, "") + ".conf";
      }
      return /\.json$/i.test(base) ? base : base + ".json";
    }
    var version = String((state.doc && state.doc.version) || state.selectedVersion || "config").replace(/[^\w.-]+/g, "-");
    var configType = String((state.doc && state.doc.configType) || state.configType || "fluentbit").replace(/[^\w.-]+/g, "-");
    return "config-service-" + configType + "-" + version + (state.configType === "fluentd" ? ".conf" : ".json");
  }

  function downloadBlob(fileName, blob) {
    var url = window.URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  }

  function shouldPromptForSaveLocation() {
    var name = String(state.currentFileName || "").trim();
    if (!name) {
      return true;
    }
    return /^new-\d+$/i.test(name);
  }

  function pickerTypesForCurrentConfig() {
    if (state.configType === "fluentd") {
      return [
        {
          description: "Fluentd configuration",
          accept: {
            "text/plain": [".conf"],
          },
        },
      ];
    }
    return [
      {
        description: "Config Service JSON document",
        accept: {
          "application/json": [".json"],
        },
      },
    ];
  }

  function buildSaveBlob() {
    if (state.configType === "fluentd") {
      return fetchJson(API_BASE + "/render/fluentd/" + encodeURIComponent(state.doc.version), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config: state.doc.config,
          annotations: state.doc.annotations || {},
        }),
      }).then(function (result) {
        var renderedText = prependConfigHeader(result.text || "", state.configType, state.doc.version, "#");
        return {
          blob: new Blob([renderedText], { type: "text/plain" }),
          text: renderedText,
        };
      });
    }
    var jsonText = prependConfigHeader(JSON.stringify(state.doc, null, 2), state.configType, state.doc.version, "//");
    return Promise.resolve({
      blob: new Blob([jsonText], { type: "application/json" }),
      text: jsonText,
    });
  }

  function writeToSaveHandle(handle, blob) {
    return handle.createWritable().then(function (writable) {
      return writable.write(blob).then(function () {
        return writable.close();
      });
    });
  }

  function currentApiQuery() {
    return "?config_type=" + encodeURIComponent(state.configType || "fluentbit");
  }

  function triggerConfigDownload(forcePrompt) {
    if (!state.doc) {
      setStatusMessage("Nothing to save yet.");
      return;
    }
    var fileName = defaultSaveFileName();
    buildSaveBlob()
      .then(function (result) {
        if ((forcePrompt || state.saveFileHandle || shouldPromptForSaveLocation()) && typeof window.showSaveFilePicker === "function") {
          var handlePromise = !forcePrompt && state.saveFileHandle
            ? Promise.resolve(state.saveFileHandle)
            : window.showSaveFilePicker({
                suggestedName: fileName,
                types: pickerTypesForCurrentConfig(),
              });
          return handlePromise.then(function (handle) {
            state.saveFileHandle = handle;
            return writeToSaveHandle(handle, result.blob).then(function () {
              state.currentFileName = handle.name || fileName;
              setOpenFileDisplay(handle.name || fileName);
              setCookie(LAST_FILE_COOKIE, state.currentFileName);
              saveDoc();
              setStatusMessage("Saved configuration as " + state.currentFileName);
            });
          });
        }

        downloadBlob(fileName, result.blob);
        state.currentFileName = fileName;
        setOpenFileDisplay(fileName);
        setCookie(LAST_FILE_COOKIE, fileName);
        saveDoc();
        setStatusMessage("Saved configuration as " + fileName);
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") {
          setStatusMessage("Save cancelled.");
          return;
        }
        setValidationText(String(err));
      });
  }

  function updateAddPluginState() {
    var hasCatalog = Boolean(state.catalog && state.catalog.plugins);
    var hasPluginValue = Boolean(el.pluginName && el.pluginName.value);
    el.addPlugin.disabled = isReadOnlyMode() || !(hasCatalog && hasPluginValue);
  }

  function updateFluentdSectionVisibility() {
    var show = isFluentdMode();
    el.labelsPanel.classList.toggle("hidden", !show);
    el.workersPanel.classList.toggle("hidden", !show);
  }

  function selectedPluginDefinition() {
    var groups = pluginGroups();
    var selectedPluginName = String(el.pluginName.value || state.pluginName || "").trim();
    if (!selectedPluginName) {
      return null;
    }
    return (groups[state.pluginSection] && groups[state.pluginSection][selectedPluginName]) || null;
  }

  function fluentbitProcessorRoot() {
    if (!state.catalog || !state.catalog.common || !state.catalog.common.processors) {
      return null;
    }
    return state.catalog.common.processors;
  }

  function fluentbitProcessorSignals() {
    var root = fluentbitProcessorRoot();
    return (root && root.signals) || {};
  }

  function fluentbitSignalProcessorMap(signalName) {
    var signals = fluentbitProcessorSignals();
    var signalDef = signals[signalName] || {};
    var available = {};
    Object.keys(signalDef.processors || {}).forEach(function (name) {
      available[name] = signalDef.processors[name];
    });
    if (signalName === "logs" && signalDef.allow_filters_as_processors && state.catalog && state.catalog.plugins) {
      var filterDefs = state.catalog.plugins.filters || {};
      Object.keys(filterDefs).forEach(function (name) {
        available[name] = filterDefs[name];
      });
    }
    return available;
  }

  function fluentbitProcessorDefinition(signalName, processorName) {
    return fluentbitSignalProcessorMap(signalName)[processorName] || null;
  }

  function ensureFluentbitProcessors(instance) {
    if (!instance.processors || typeof instance.processors !== "object") {
      instance.processors = {};
    }
    ["logs", "metrics", "traces"].forEach(function (signalName) {
      if (!Array.isArray(instance.processors[signalName])) {
        instance.processors[signalName] = [];
      }
    });
  }

  function getPluginDefinition(section, pluginName) {
    var groups = pluginGroups();
    return (groups[section] && groups[section][pluginName]) || null;
  }

  function updatePluginHelpState() {
    var pluginDef = selectedPluginDefinition();
    var selectedPluginName = String(el.pluginName.value || state.pluginName || "").trim();
    if (!pluginDef || !pluginDef.doc_url) {
      el.pluginHelpToggle.disabled = true;
      el.pluginHelpToggle.title = selectedPluginName
        ? "No linked documentation is available for this plugin."
        : "Select a plugin to view help.";
      return;
    }

    el.pluginHelpToggle.disabled = false;
    el.pluginHelpToggle.title = selectedPluginName + ": " + String(pluginDef.description || "Open plugin documentation.");
  }

  function createFieldHelpButton(field, alignRight) {
    var helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.textContent = "?";
    helpBtn.className = "icon-help";
    if (alignRight) {
      helpBtn.classList.add("right-align");
    }
    var description = String(field.description || "Open field documentation.");
    var reference = String(field.reference || "").trim();
    helpBtn.title = reference ? description + " (" + reference + ")" : description;
    if (!reference) {
      helpBtn.disabled = true;
      return helpBtn;
    }
    helpBtn.setAttribute("aria-label", "Open help for " + field.name);
    helpBtn.addEventListener("click", function () {
      window.open(reference, "_blank", "noopener,noreferrer");
    });
    return helpBtn;
  }

  function renderFieldRow(instance, field, options) {
    options = options || {};
    var block = document.createElement("div");
    block.className = "field-block";
    if (options.commentTarget && options.commentFieldName) {
      block.classList.add("comment-group");
    }

    var row = document.createElement("div");
    row.className = "field-row";
    if (options.optional) {
      row.classList.add("optional-field-row");
    }

    var label = document.createElement("label");
    label.textContent = field.name;
    if (field.required) {
      var required = document.createElement("span");
      required.className = "required-mark";
      required.textContent = "*";
      label.appendChild(required);
    }
    row.appendChild(label);

    var dataType = String(field.data_type || "string").toLowerCase();
    var enumOptions = getEnumOptions(field);
    if (dataType === "enum" && enumOptions.length > 0) {
      var select = document.createElement("select");
      enumOptions.forEach(function (value) {
        var option = document.createElement("option");
        option.value = String(value);
        option.textContent = String(value);
        select.appendChild(option);
      });
      select.value = normalizeEnumAliasValue(
        enumOptions,
        fieldInputValue(instance[field.name], field.data_type) || String(enumOptions[0])
      ) || String(enumOptions[0]);
      if (options.focusKey && state.pendingFocusFieldKey === options.focusKey) {
        setTimeout(function () {
          select.focus();
        }, 0);
        state.pendingFocusFieldKey = "";
      }
      select.addEventListener("change", function () {
        instance[field.name] = select.value;
        saveDoc();
      });
      select.disabled = isReadOnlyMode();
      row.appendChild(select);
    } else if (dataType === "boolean") {
      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(instance[field.name]);
      if (options.focusKey && state.pendingFocusFieldKey === options.focusKey) {
        setTimeout(function () {
          checkbox.focus();
        }, 0);
        state.pendingFocusFieldKey = "";
      }
      checkbox.addEventListener("change", function () {
        instance[field.name] = checkbox.checked;
        saveDoc();
      });
      checkbox.disabled = isReadOnlyMode();
      row.appendChild(checkbox);
    } else {
      var isStructured = dataType === "array" || dataType === "list" || dataType === "object" || dataType === "map";
      var isCode = dataType === "code";
      var input = isStructured || isCode ? document.createElement("textarea") : document.createElement("input");
      input.value = fieldInputValue(instance[field.name], field.data_type);
      input.placeholder = field.description || "";
      input.title = (field.reference || "") + "\n" + (field.description || "");
      if (isCode) {
        prepareCodeTextarea(input);
      }
      if (options.focusKey && state.pendingFocusFieldKey === options.focusKey) {
        setTimeout(function () {
          input.focus();
          if (typeof input.select === "function") {
            input.select();
          }
          if (isCode) {
            resizeCodeTextarea(input);
          }
        }, 0);
        state.pendingFocusFieldKey = "";
      }
      input.addEventListener("change", function () {
        instance[field.name] = parseTextValue(input.value, field.data_type);
        saveDoc();
      });
      input.disabled = isReadOnlyMode();
      row.appendChild(input);
    }

    row.appendChild(createFieldHelpButton(field, false));

    if (options.commentTarget && options.commentFieldName) {
      var commentToggle = createCommentToggleButton(
        options.commentToggleKey || "",
        options.commentTarget,
        options.commentFieldName,
        "comment editor for " + options.commentFieldName
      );
      commentToggle.classList.add("right-align");
      row.appendChild(commentToggle);
    }

    if (options.optional && typeof options.onRemove === "function") {
      var removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "-";
      removeBtn.className = "icon-remove right-align";
      removeBtn.title = "Remove attribute";
      removeBtn.disabled = isReadOnlyMode();
      removeBtn.addEventListener("click", options.onRemove);
      row.appendChild(removeBtn);
    }

    block.appendChild(row);
    if (options.commentTarget && options.commentFieldName) {
      block.appendChild(
        createCommentEditorPanel(
          options.commentTarget,
          "Comment",
          options.commentFieldName,
          options.commentToggleKey || ""
        )
      );
    }

    return block;
  }

  function moveWithinPipeline(pipeline, section, index, direction, pathPrefix) {
    if (isReadOnlyMode()) {
      return;
    }
    var list = pipeline[section];
    var target = index + direction;
    if (target < 0 || target >= list.length) {
      return;
    }
    if (pathPrefix) {
    }
    var temp = list[target];
    list[target] = list[index];
    list[index] = temp;
    saveDoc();
    renderAll();
  }

  function remapPluginInstanceForSection(instance, targetPluginDef) {
    var nextInstance = { name: instance.name };
    var targetFields = (targetPluginDef && targetPluginDef.fields) || [];
    targetFields.forEach(function (field) {
      if (Object.prototype.hasOwnProperty.call(instance, field.name)) {
        nextInstance[field.name] = instance[field.name];
        return;
      }
      if (field.required) {
        nextInstance[field.name] = defaultForField(field);
      }
    });
    return nextInstance;
  }

  function movePluginToSection(pipeline, section, index, instance, targetSection, pathPrefix) {
    if (isReadOnlyMode()) {
      return;
    }
    if (targetSection === section) {
      return;
    }
    var targetPluginDef = getPluginDefinition(targetSection, instance.name);
    if (!targetPluginDef) {
      setValidationText(
        "Plugin '" + instance.name + "' is not available in the '" + targetSection + "' section."
      );
      return;
    }
    var nextInstance = remapPluginInstanceForSection(instance, targetPluginDef);
    if (pathPrefix) {
    }
    pipeline[section].splice(index, 1);
    pipeline[targetSection].push(nextInstance);
    saveDoc();
    setValidationText("");
    renderAll();
  }

  function renderProcessorCondition(instance, procPathPrefix) {
    var frame = document.createElement("div");
    frame.className = "nested-panel";
    var title = document.createElement("h4");
    title.textContent = "Condition";
    frame.appendChild(title);

    var row = document.createElement("div");
    row.className = "field-row";

    var opLabel = document.createElement("label");
    opLabel.textContent = "Operator";
    row.appendChild(opLabel);

    var opSelect = document.createElement("select");
    ["and", "or"].forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      opSelect.appendChild(option);
    });
    opSelect.value = String((instance.condition && instance.condition.op) || "and");
    opSelect.addEventListener("change", function () {
      if (isReadOnlyMode()) {
        return;
      }
      if (!instance.condition || typeof instance.condition !== "object") {
        instance.condition = { op: "and", rules: [] };
      }
      instance.condition.op = opSelect.value;
      saveDoc();
    });
    opSelect.disabled = isReadOnlyMode();
    row.appendChild(opSelect);
    frame.appendChild(row);

    var rulesRow = document.createElement("div");
    rulesRow.className = "field-row";
    var rulesLabel = document.createElement("label");
    rulesLabel.textContent = "Rules JSON";
    rulesRow.appendChild(rulesLabel);
    var rulesInput = document.createElement("textarea");
    try {
      rulesInput.value = JSON.stringify((instance.condition && instance.condition.rules) || [], null, 2);
    } catch (_e) {
      rulesInput.value = "[]";
    }
    rulesInput.placeholder = '[{"field":"$level","op":"eq","value":"error"}]';
    rulesInput.addEventListener("change", function () {
      if (isReadOnlyMode()) {
        return;
      }
      if (!instance.condition || typeof instance.condition !== "object") {
        instance.condition = { op: opSelect.value, rules: [] };
      }
      try {
        var parsed = JSON.parse(rulesInput.value || "[]");
        instance.condition.rules = Array.isArray(parsed) ? parsed : [];
      } catch (_err) {
        instance.condition.rules = [];
      }
      saveDoc();
    });
    rulesInput.disabled = isReadOnlyMode();
    rulesRow.appendChild(rulesInput);
    frame.appendChild(rulesRow);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "-";
    removeBtn.className = "icon-remove";
    removeBtn.title = "Remove condition";
    removeBtn.disabled = isReadOnlyMode();
    removeBtn.addEventListener("click", function () {
      delete instance.condition;
      saveDoc();
      renderAll();
    });
    frame.appendChild(removeBtn);

    return frame;
  }

  function renderProcessorCard(signalName, processorIndex, processorInstance, keyPrefix, collection, processorPath) {
    var procDef = fluentbitProcessorDefinition(signalName, processorInstance.name);
    var card = document.createElement("div");
    card.className = "plugin-card";

    var key = keyPrefix + ":processor:" + signalName + ":" + processorIndex;
    var collapsed = Boolean(state.collapse[key]);

    var head = document.createElement("div");
    head.className = "plugin-head";

    var left = document.createElement("div");
    left.className = "plugin-head-main";
    var title = document.createElement("strong");
    title.textContent = "#" + (processorIndex + 1) + " " + processorInstance.name + " (" + signalName + ")";
    left.appendChild(title);
    head.appendChild(left);

    var actions = document.createElement("div");
    actions.className = "plugin-actions";

    actions.appendChild(
      createCommentToggleButton(
        key + ":comment",
        processorInstance,
        "",
        "processor comment editor"
      )
    );

    var collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.textContent = collapsed ? "Expand" : "Collapse";
    collapseBtn.addEventListener("click", function () {
      state.collapse[key] = !collapsed;
      renderAll();
    });
    actions.appendChild(collapseBtn);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "-";
    removeBtn.className = "icon-remove";
    removeBtn.title = "Remove processor";
    removeBtn.disabled = isReadOnlyMode();
    removeBtn.addEventListener("click", function () {
      collection.splice(processorIndex, 1);
      saveDoc();
      renderAll();
    });
    actions.appendChild(removeBtn);

    head.appendChild(actions);
    card.appendChild(head);

    if (collapsed) {
      return card;
    }

    var fieldsWrap = document.createElement("div");
    fieldsWrap.className = "field-grid";
    var fields = (procDef && procDef.fields) || [];
    var requiredFields = fields.filter(function (field) {
      return field.required;
    });
    var currentOptionalFields = fields.filter(function (field) {
      return !field.required && Object.prototype.hasOwnProperty.call(processorInstance, field.name);
    });

    requiredFields.forEach(function (field) {
      fieldsWrap.appendChild(
        renderFieldRow(processorInstance, field, {
          optional: false,
          focusKey: key + ":" + field.name,
          commentTarget: processorInstance,
          commentFieldName: field.name,
          commentToggleKey: key + ":" + field.name + ":comment",
        })
      );
    });

    currentOptionalFields.forEach(function (field) {
      fieldsWrap.appendChild(
        renderFieldRow(processorInstance, field, {
          optional: true,
          focusKey: key + ":" + field.name,
          commentTarget: processorInstance,
          commentFieldName: field.name,
          commentToggleKey: key + ":" + field.name + ":comment",
          onRemove: function () {
            delete processorInstance[field.name];
            saveDoc();
            renderAll();
          },
        })
      );
    });
    card.appendChild(createCommentEditorPanel(processorInstance, "Processor Comment", "", key + ":comment"));
    card.appendChild(fieldsWrap);

    var missingOptional = fields.filter(function (field) {
      return !field.required && !Object.prototype.hasOwnProperty.call(processorInstance, field.name);
    });
    if (missingOptional.length > 0) {
      var optionalRow = document.createElement("div");
      optionalRow.className = "optional-row";
      var optionalSel = document.createElement("select");
      var emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = "Select optional processor attribute...";
      optionalSel.appendChild(emptyOpt);
      missingOptional.forEach(function (field) {
        var opt = document.createElement("option");
        opt.value = field.name;
        opt.textContent = field.name;
        optionalSel.appendChild(opt);
      });
      optionalRow.appendChild(optionalSel);

      var optionalDivider = document.createElement("span");
      optionalDivider.className = "optional-divider";
      optionalDivider.setAttribute("aria-hidden", "true");
      optionalRow.appendChild(optionalDivider);

      var addOptional = document.createElement("button");
      addOptional.type = "button";
      addOptional.textContent = "Add Optional";
      addOptional.addEventListener("click", function () {
        var selected = optionalSel.value;
        if (!selected) {
          return;
        }
        var field = fields.find(function (item) {
          return item.name === selected;
        });
        if (!field) {
          return;
        }
        processorInstance[field.name] = defaultForField(field);
        saveDoc();
        renderAll();
      });
      optionalRow.appendChild(addOptional);
      card.appendChild(optionalRow);
    }

    if (procDef && procDef.supports_condition) {
      var conditionWrap = document.createElement("div");
      conditionWrap.className = "nested-panel";
      if (processorInstance.condition && typeof processorInstance.condition === "object") {
        card.appendChild(renderProcessorCondition(processorInstance, key));
      } else {
        var addCondition = document.createElement("button");
        addCondition.type = "button";
        addCondition.textContent = "Add Condition";
        addCondition.addEventListener("click", function () {
          processorInstance.condition = { op: "and", rules: [] };
          saveDoc();
          renderAll();
        });
        conditionWrap.appendChild(addCondition);
        card.appendChild(conditionWrap);
      }
    }

    return card;
  }

  function renderFluentbitProcessorsPanel(section, index, instance, keyPrefix, pluginPath) {
    ensureFluentbitProcessors(instance);

    var frame = document.createElement("div");
    frame.className = "nested-panel";

    var heading = document.createElement("h4");
    heading.textContent = "Processors";
    frame.appendChild(heading);

    var controls = document.createElement("div");
    controls.className = "row";

    var signalLabel = document.createElement("label");
    signalLabel.textContent = "Signal";
    var signalSelect = document.createElement("select");
    Object.keys(fluentbitProcessorSignals()).forEach(function (signalName) {
      var option = document.createElement("option");
      option.value = signalName;
      option.textContent = signalName;
      signalSelect.appendChild(option);
    });
    signalLabel.appendChild(signalSelect);
    controls.appendChild(signalLabel);

    var procLabel = document.createElement("label");
    procLabel.textContent = "Processor";
    var procSelect = document.createElement("select");
    procLabel.appendChild(procSelect);
    controls.appendChild(procLabel);

    var helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.textContent = "?";
    helpBtn.className = "icon-help";
    controls.appendChild(helpBtn);

    var addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.textContent = "Add Processor";
    controls.appendChild(addBtn);

    function refreshProcessorSelect() {
      var signalName = signalSelect.value;
      var available = fluentbitSignalProcessorMap(signalName);
      var names = Object.keys(available).sort();
      procSelect.innerHTML = "";
      names.forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        procSelect.appendChild(option);
      });
      var def = names.length > 0 ? available[names[0]] : null;
      helpBtn.disabled = !(def && def.doc_url);
      helpBtn.title = def && def.description ? def.description : "Open processor documentation.";
    }

    signalSelect.addEventListener("change", refreshProcessorSelect);
    procSelect.addEventListener("change", function () {
      var def = fluentbitProcessorDefinition(signalSelect.value, procSelect.value);
      helpBtn.disabled = !(def && def.doc_url);
      helpBtn.title = def && def.description ? def.description : "Open processor documentation.";
    });
    helpBtn.addEventListener("click", function () {
      var def = fluentbitProcessorDefinition(signalSelect.value, procSelect.value);
      if (!def || !def.doc_url) {
        setValidationText("No linked processor documentation is available for the current selection.");
        return;
      }
      window.open(def.doc_url, "_blank", "noopener,noreferrer");
    });
    addBtn.addEventListener("click", function () {
      var signalName = signalSelect.value;
      var processorName = procSelect.value;
      var def = fluentbitProcessorDefinition(signalName, processorName);
      if (!def) {
        return;
      }
      var item = { name: processorName };
      (def.fields || []).forEach(function (field) {
        if (field.required) {
          item[field.name] = defaultForField(field);
        }
      });
      instance.processors[signalName].push(item);
      saveDoc();
      renderAll();
    });
    refreshProcessorSelect();
    frame.appendChild(controls);

    ["logs", "metrics", "traces"].forEach(function (signalName) {
      var items = instance.processors[signalName];
      if (!Array.isArray(items) || items.length === 0) {
        return;
      }
      var signalWrap = document.createElement("div");
      signalWrap.className = "container-stack";
      var signalTitle = document.createElement("h4");
      signalTitle.textContent = signalName;
      signalWrap.appendChild(signalTitle);
      items.forEach(function (processorInstance, processorIndex) {
        signalWrap.appendChild(
          renderProcessorCard(
            signalName,
            processorIndex,
            processorInstance,
            keyPrefix + ":" + section + ":" + index,
            items,
            pluginPath + ".processors." + signalName + "[" + processorIndex + "]"
          )
        );
      });
      frame.appendChild(signalWrap);
    });

    return frame;
  }

  function renderPluginCard(flatIndex, section, index, instance, pipeline, keyPrefix, pathPrefix) {
    var groups = pluginGroups();
    var pluginDef = groups[section][instance.name];
    var card = document.createElement("div");
    card.className = "plugin-card";

    var key = (keyPrefix || "main") + ":" + section + "-" + index;
    var pluginPath = (pathPrefix || "$.pipeline") + "." + section + "[" + index + "]";
    var collapsed = Boolean(state.collapse[key]);

    var head = document.createElement("div");
    head.className = "plugin-head";

    var left = document.createElement("div");
    left.className = "plugin-head-main";
    var title = document.createElement("strong");
    title.textContent = "#" + (flatIndex + 1) + " " + instance.name;
    left.appendChild(title);

    var sectionIcons = document.createElement("div");
    sectionIcons.className = "section-icon-group";
    [
      { key: "inputs", label: "I", title: "Input" },
      { key: "filters", label: "F", title: "Filter" },
      { key: "outputs", label: "O", title: "Output" },
    ].forEach(function (sectionMeta) {
      var targetPluginDef = getPluginDefinition(sectionMeta.key, instance.name);
      var iconBtn = document.createElement("button");
      iconBtn.type = "button";
      iconBtn.textContent = sectionMeta.label;
      iconBtn.className = "section-icon";
      if (sectionMeta.key === section) {
        iconBtn.classList.add("is-active");
      }
      if (!targetPluginDef) {
        iconBtn.disabled = true;
        iconBtn.classList.add("is-disabled");
      } else if (isReadOnlyMode()) {
        iconBtn.disabled = true;
      }
      iconBtn.title = sectionMeta.title;
      iconBtn.setAttribute(
        "aria-label",
        targetPluginDef
          ? "Move plugin to " + sectionMeta.title + " section"
          : sectionMeta.title + " section unavailable for this plugin"
      );
      if (targetPluginDef && sectionMeta.key !== section) {
        iconBtn.addEventListener("click", function () {
          movePluginToSection(pipeline, section, index, instance, sectionMeta.key, pathPrefix || "$.pipeline");
        });
      }
      sectionIcons.appendChild(iconBtn);
    });
    left.appendChild(sectionIcons);

    head.appendChild(left);

    var actions = document.createElement("div");
    actions.className = "plugin-actions";

    actions.appendChild(createCommentToggleButton(key + ":comment", instance, "", "plugin comment editor"));

    var collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.textContent = collapsed ? "Expand" : "Collapse";
    collapseBtn.addEventListener("click", function () {
      state.collapse[key] = !collapsed;
      renderAll();
    });
    actions.appendChild(collapseBtn);

    var upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.textContent = "↑";
    upBtn.className = "icon-button";
    upBtn.title = "Move plugin up";
    upBtn.disabled = isReadOnlyMode() || index === 0;
    upBtn.addEventListener("click", function () {
      moveWithinPipeline(pipeline, section, index, -1, pathPrefix || "$.pipeline");
    });
    actions.appendChild(upBtn);

    var downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.textContent = "↓";
    downBtn.className = "icon-button";
    downBtn.title = "Move plugin down";
    downBtn.disabled = isReadOnlyMode() || index >= pipeline[section].length - 1;
    downBtn.addEventListener("click", function () {
      moveWithinPipeline(pipeline, section, index, 1, pathPrefix || "$.pipeline");
    });
    actions.appendChild(downBtn);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "-";
    removeBtn.className = "icon-remove";
    removeBtn.title = "Remove plugin";
    removeBtn.disabled = isReadOnlyMode();
    removeBtn.addEventListener("click", function () {
      pipeline[section].splice(index, 1);
      saveDoc();
      renderAll();
    });
    actions.appendChild(removeBtn);

    head.appendChild(actions);
    card.appendChild(head);

    if (!collapsed) {
      card.appendChild(createCommentEditorPanel(instance, "Plugin Comment", "", key + ":comment"));

      var fieldsWrap = document.createElement("div");
      fieldsWrap.className = "field-grid";

      var fields = (pluginDef && pluginDef.fields) || [];
      var requiredFields = fields.filter(function (field) {
        return field.required;
      });
      var currentOptionalFields = fields.filter(function (field) {
        return !field.required && Object.prototype.hasOwnProperty.call(instance, field.name);
      });

      requiredFields.forEach(function (field) {
        var focusKey = section + ":" + index + ":" + field.name;
        fieldsWrap.appendChild(
          renderFieldRow(instance, field, {
            optional: false,
            focusKey: focusKey,
            onRemove: null,
            commentTarget: instance,
            commentFieldName: field.name,
            commentToggleKey: key + ":" + field.name + ":comment",
          })
        );
      });

      currentOptionalFields.forEach(function (field) {
        var focusKey = section + ":" + index + ":" + field.name;
        fieldsWrap.appendChild(
          renderFieldRow(instance, field, {
            optional: true,
            focusKey: focusKey,
            commentTarget: instance,
            commentFieldName: field.name,
            commentToggleKey: key + ":" + field.name + ":comment",
            onRemove: function () {
              delete instance[field.name];
              saveDoc();
              renderAll();
            },
          })
        );
      });

      card.appendChild(fieldsWrap);

      var missingOptional = fields.filter(function (f) {
        return !f.required && !Object.prototype.hasOwnProperty.call(instance, f.name);
      });
      if (missingOptional.length > 0) {
        var optionalRow = document.createElement("div");
        optionalRow.className = "optional-row";
        var optionalSel = document.createElement("select");
        var emptyOpt = document.createElement("option");
        emptyOpt.value = "";
        emptyOpt.textContent = "Select optional attribute...";
        optionalSel.appendChild(emptyOpt);
        missingOptional.forEach(function (f) {
          var opt = document.createElement("option");
          opt.value = f.name;
          opt.textContent = f.name;
          optionalSel.appendChild(opt);
        });
        optionalRow.appendChild(optionalSel);

        var optionalDivider = document.createElement("span");
        optionalDivider.className = "optional-divider";
        optionalDivider.setAttribute("aria-hidden", "true");
        optionalRow.appendChild(optionalDivider);

        var addOptional = document.createElement("button");
        addOptional.type = "button";
        addOptional.textContent = "Add Optional";
        addOptional.disabled = isReadOnlyMode();
        addOptional.addEventListener("click", function () {
          var selected = optionalSel.value;
          if (!selected) {
            return;
          }
          var field = fields.find(function (f) {
            return f.name === selected;
          });
          if (!field) {
            return;
          }
          instance[field.name] = defaultForField(field);
          state.pendingFocusFieldKey = section + ":" + index + ":" + field.name;
          saveDoc();
          renderAll();
        });
        optionalRow.appendChild(addOptional);

        card.appendChild(optionalRow);
      }

      if (state.configType === "fluentbit" && (section === "inputs" || section === "outputs") && fluentbitProcessorRoot()) {
        card.appendChild(renderFluentbitProcessorsPanel(section, index, instance, keyPrefix || "main", pluginPath));
      }
    }

    return card;
  }

  function renderService() {
    ensureDoc();
    el.serviceList.innerHTML = "";
    var entries = Object.entries(state.doc.config.service || {});
    if (entries.length === 0) {
      var empty = document.createElement("p");
      empty.textContent = "No service settings configured.";
      el.serviceList.appendChild(empty);
      return;
    }

    var card = document.createElement("div");
    card.className = "plugin-card service-card";

    var head = document.createElement("div");
    head.className = "plugin-head";

    var left = document.createElement("div");
    left.className = "plugin-head-main";

    head.appendChild(left);

    var actions = document.createElement("div");
    actions.className = "plugin-actions";
    actions.appendChild(createMetaHelpButton());
    actions.appendChild(
      createCommentToggleButton(
        "service:comment",
        state.doc.config.service,
        "",
        "service comment editor"
      )
    );
    var collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.textContent = state.serviceCollapsed ? "Expand" : "Collapse";
    collapseBtn.addEventListener("click", function () {
      state.serviceCollapsed = !state.serviceCollapsed;
      renderService();
    });
    actions.appendChild(collapseBtn);
    head.appendChild(actions);

    card.appendChild(head);

    if (state.serviceCollapsed) {
      el.serviceList.appendChild(card);
      return;
    }

    card.appendChild(
      createCommentEditorPanel(
        state.doc.config.service,
        "Service Comment",
        "",
        "service:comment"
      )
    );

    var body = document.createElement("div");
    body.className = "field-grid";

    entries.forEach(function (entry) {
      var key = entry[0];
      var value = entry[1];
      var knownServiceOption = SERVICE_OPTION_BY_KEY[key] || null;
      var row = document.createElement("div");
      row.className = "service-row";
      if (knownServiceOption) {
        row.title = knownServiceOption.reference
          ? knownServiceOption.description + " (" + knownServiceOption.reference + ")"
          : knownServiceOption.description;
      }

      var keyInput = document.createElement("input");
      keyInput.value = key;
      keyInput.disabled = isReadOnlyMode();
      keyInput.addEventListener("change", function () {
        var newKey = keyInput.value.trim();
        if (!newKey || newKey === key) {
          keyInput.value = key;
          return;
        }
        renameFieldComment(state.doc.config.service, key, newKey);
        state.doc.config.service[newKey] = state.doc.config.service[key];
        delete state.doc.config.service[key];
        saveDoc();
        renderService();
      });
      row.appendChild(keyInput);

      var valueInput = document.createElement("input");
      var serviceDataType = knownServiceOption ? String(knownServiceOption.data_type || "").toLowerCase() : "";
      if (knownServiceOption && serviceDataType === "enum") {
        valueInput = document.createElement("select");
        var serviceEnumOptions = getEnumOptions(knownServiceOption);
        serviceEnumOptions.forEach(function (enumValue) {
          var option = document.createElement("option");
          option.value = String(enumValue);
          option.textContent = String(enumValue);
          valueInput.appendChild(option);
        });
        valueInput.value = String(normalizeEnumAliasValue(serviceEnumOptions, value));
        valueInput.disabled = isReadOnlyMode();
      } else if (knownServiceOption && serviceDataType === "code") {
        valueInput = document.createElement("textarea");
        if (typeof value === "object") {
          try {
            valueInput.value = JSON.stringify(value, null, 2);
          } catch (_e) {
            valueInput.value = String(value);
          }
        } else {
          valueInput.value = String(value);
        }
        prepareCodeTextarea(valueInput);
        valueInput.disabled = isReadOnlyMode();
      } else {
        valueInput = document.createElement("input");
        if (typeof value === "object") {
          try {
            valueInput.value = JSON.stringify(value);
          } catch (_e) {
            valueInput.value = String(value);
          }
        } else {
          valueInput.value = String(value);
        }
        valueInput.disabled = isReadOnlyMode();
      }
      valueInput.addEventListener("change", function () {
        if (knownServiceOption) {
          state.doc.config.service[key] = parseServiceValueByType(
            valueInput.value,
            knownServiceOption.data_type
          );
        } else {
          state.doc.config.service[key] = parseServiceValue(valueInput.value);
        }
        saveDoc();
      });
      row.appendChild(valueInput);

      row.appendChild(
        createFieldHelpButton(
          {
            name: key,
            description: knownServiceOption ? knownServiceOption.description : "No linked service attribute documentation available.",
            reference: knownServiceOption ? knownServiceOption.reference : "",
          },
          false
        )
      );

      row.appendChild(
        createCommentToggleButton(
          "service:" + key + ":comment",
          state.doc.config.service,
          key,
          "comment editor for " + key
        )
      );

      var removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "-";
      removeBtn.className = "icon-remove right-align";
      removeBtn.title = "Remove service field";
      removeBtn.disabled = isReadOnlyMode();
      removeBtn.addEventListener("click", function () {
        clearFieldComment(state.doc.config.service, key);
        delete state.doc.config.service[key];
        saveDoc();
        renderService();
      });
      row.appendChild(removeBtn);

      var block = document.createElement("div");
      block.className = "field-block";
      block.classList.add("comment-group");
      block.appendChild(row);
      block.appendChild(
        createCommentEditorPanel(
          state.doc.config.service,
          "Comment",
          key,
          "service:" + key + ":comment"
        )
      );
      body.appendChild(block);
    });

    card.appendChild(body);
    el.serviceList.appendChild(card);
  }

  function renderPlugins() {
    ensureDoc();
    el.pluginList.innerHTML = "";
    var flattened = flattenPlugins();
    if (flattened.length === 0) {
      var empty = document.createElement("p");
      empty.textContent = "No plugins yet. Use Add Plugin to create entries.";
      el.pluginList.appendChild(empty);
      return;
    }

    flattened.forEach(function (entry, flatIndex) {
      el.pluginList.appendChild(
        renderPluginCard(flatIndex, entry.section, entry.index, entry.instance, state.doc.config.pipeline, "main", "$.pipeline")
      );
    });
  }

  function nextLabelName() {
    ensureDoc();
    return "@label" + String((state.doc.config.labels || []).length + 1);
  }

  function nextWorkerName() {
    ensureDoc();
    return String((state.doc.config.workers || []).length);
  }

  function createScopedPluginAdder(pipeline, prefix) {
    var row = document.createElement("div");
    row.className = "nested-panel";

    var heading = document.createElement("h4");
    heading.textContent = "Add Plugin";
    row.appendChild(heading);

    var controls = document.createElement("div");
    controls.className = "row";

    var sectionLabel = document.createElement("label");
    sectionLabel.textContent = "Section";
    var sectionSelect = document.createElement("select");
    ["inputs", "filters", "outputs"].forEach(function (sectionName) {
      var option = document.createElement("option");
      option.value = sectionName;
      option.textContent = sectionName;
      sectionSelect.appendChild(option);
    });
    sectionLabel.appendChild(sectionSelect);
    controls.appendChild(sectionLabel);

    var pluginLabel = document.createElement("label");
    pluginLabel.textContent = "Plugin";
    var pluginSelect = document.createElement("select");
    pluginLabel.appendChild(pluginSelect);
    controls.appendChild(pluginLabel);

    var helpBtn = document.createElement("button");
    helpBtn.type = "button";
    helpBtn.textContent = "?";
    helpBtn.className = "icon-help";
    controls.appendChild(helpBtn);

    var addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.textContent = "Add Plugin";
    controls.appendChild(addBtn);

    function refreshPluginSelect() {
      var section = sectionSelect.value;
      var names = Object.keys(pluginGroups()[section] || {}).sort();
      pluginSelect.innerHTML = "";
      names.forEach(function (name) {
        var option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        pluginSelect.appendChild(option);
      });
      helpBtn.disabled = names.length === 0;
      if (names.length > 0) {
        var def = getPluginDefinition(section, names[0]);
        helpBtn.title = def && def.description ? def.description : "Open plugin documentation.";
      }
    }

    sectionSelect.addEventListener("change", refreshPluginSelect);
    sectionSelect.disabled = isReadOnlyMode();
    pluginSelect.addEventListener("change", function () {
      var def = getPluginDefinition(sectionSelect.value, pluginSelect.value);
      helpBtn.disabled = !(def && def.doc_url);
      helpBtn.title = def && def.description ? def.description : "Open plugin documentation.";
    });
    helpBtn.addEventListener("click", function () {
      var def = getPluginDefinition(sectionSelect.value, pluginSelect.value);
      if (!def || !def.doc_url) {
        setValidationText("No linked documentation is available for the selected Fluentd plugin.");
        return;
      }
      window.open(def.doc_url, "_blank", "noopener,noreferrer");
    });
    pluginSelect.disabled = isReadOnlyMode();
    addBtn.addEventListener("click", function () {
      var section = sectionSelect.value;
      var name = pluginSelect.value;
      var def = getPluginDefinition(section, name);
      if (!def) {
        return;
      }
      var instance = { name: name };
      (def.fields || []).forEach(function (field) {
        if (field.required) {
          instance[field.name] = defaultForField(field);
        }
      });
      pipeline[section].push(instance);
      saveDoc();
      renderAll();
    });
    addBtn.disabled = isReadOnlyMode();

    refreshPluginSelect();
    row.appendChild(controls);
    return row;
  }

  function renderContainerPlugins(target, pipeline, prefix, pathPrefix) {
    var flattened = flattenPipeline(pipeline, prefix);
    if (flattened.length === 0) {
      var empty = document.createElement("p");
      empty.textContent = "No plugins configured in this scope yet.";
      target.appendChild(empty);
      return;
    }
    flattened.forEach(function (entry, flatIndex) {
      target.appendChild(
        renderPluginCard(flatIndex, entry.section, entry.index, entry.instance, pipeline, prefix, pathPrefix)
      );
    });
  }

  function renderNamedContainerCard(kind, collection, index, item) {
    if (!item.pipeline || typeof item.pipeline !== "object") {
      item.pipeline = { inputs: [], filters: [], outputs: [] };
    }
    ["inputs", "filters", "outputs"].forEach(function (sectionName) {
      if (!Array.isArray(item.pipeline[sectionName])) {
        item.pipeline[sectionName] = [];
      }
    });
    var card = document.createElement("div");
    card.className = "plugin-card";
    var collapseKey = kind + ":" + index;
    var collapsed = Boolean(state.collapse[collapseKey]);

    var head = document.createElement("div");
    head.className = "plugin-head";

    var left = document.createElement("div");
    left.className = "plugin-head-main";
    var title = document.createElement("strong");
    title.textContent = "#" + (index + 1) + " " + (kind === "label" ? "Label" : "Worker");
    left.appendChild(title);
    head.appendChild(left);

    var actions = document.createElement("div");
    actions.className = "plugin-actions";
    actions.appendChild(createCommentToggleButton(collapseKey + ":comment", item, "", kind + " comment editor"));

    var collapseBtn = document.createElement("button");
    collapseBtn.type = "button";
    collapseBtn.textContent = collapsed ? "Expand" : "Collapse";
    collapseBtn.addEventListener("click", function () {
      state.collapse[collapseKey] = !collapsed;
      renderAll();
    });
    actions.appendChild(collapseBtn);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "-";
    removeBtn.className = "icon-remove";
    removeBtn.title = "Remove " + kind;
    removeBtn.disabled = isReadOnlyMode();
    removeBtn.addEventListener("click", function () {
      collection.splice(index, 1);
      saveDoc();
      renderAll();
    });
    actions.appendChild(removeBtn);

    head.appendChild(actions);
    card.appendChild(head);

    if (collapsed) {
      return card;
    }

    var meta = document.createElement("div");
    meta.className = "container-meta-row";
    var nameLabel = document.createElement("label");
    nameLabel.textContent = "Name";
    var nameInput = document.createElement("input");
    nameInput.value = String(item.name || "");
    nameInput.disabled = isReadOnlyMode();
    nameInput.addEventListener("change", function () {
      item.name = nameInput.value.trim();
      saveDoc();
    });
    nameLabel.appendChild(nameInput);
    meta.appendChild(nameLabel);
    card.appendChild(meta);
    card.appendChild(createCommentEditorPanel(item, "Comment", "", collapseKey + ":comment"));

    card.appendChild(createScopedPluginAdder(item.pipeline, kind + ":" + index));

    var pluginHolder = document.createElement("div");
    pluginHolder.className = "container-stack";
    renderContainerPlugins(pluginHolder, item.pipeline, kind + ":" + index, "$." + kind + "s[" + index + "].pipeline");
    card.appendChild(pluginHolder);

    return card;
  }

  function renderLabelsAndWorkers() {
    ensureDoc();
    updateFluentdSectionVisibility();
    if (!isFluentdMode()) {
      return;
    }

    el.labelList.innerHTML = "";
    if (!Array.isArray(state.doc.config.labels) || state.doc.config.labels.length === 0) {
      var emptyLabels = document.createElement("p");
      emptyLabels.textContent = "No labels configured.";
      el.labelList.appendChild(emptyLabels);
    } else {
      state.doc.config.labels.forEach(function (label, index) {
        el.labelList.appendChild(renderNamedContainerCard("label", state.doc.config.labels, index, label));
      });
    }

    el.workerList.innerHTML = "";
    if (!Array.isArray(state.doc.config.workers) || state.doc.config.workers.length === 0) {
      var emptyWorkers = document.createElement("p");
      emptyWorkers.textContent = "No workers configured.";
      el.workerList.appendChild(emptyWorkers);
    } else {
      state.doc.config.workers.forEach(function (worker, index) {
        el.workerList.appendChild(renderNamedContainerCard("worker", state.doc.config.workers, index, worker));
      });
    }
  }

  function renderAll() {
    renderService();
    renderPlugins();
    renderLabelsAndWorkers();
    updateConfigTypeDisabledState();
    updateReadOnlyState();
    updateSectionPanels();
  }

  function loadCatalog(version) {
    return fetchJson(API_BASE + "/catalog/" + encodeURIComponent(version) + currentApiQuery()).then(function (catalog) {
      state.catalog = catalog;
      state.catalogLoaded = true;
      repopulatePluginNameSelect();
      renderAll();
      return catalog;
    });
  }

  function loadServiceOptions(version) {
    return fetchJson(API_BASE + "/service-options/" + encodeURIComponent(version) + currentApiQuery())
      .then(function (payload) {
        if (!payload || !Array.isArray(payload.options)) {
          return;
        }
        var parsed = payload.options
          .filter(function (item) {
            return item && typeof item.name === "string";
          })
          .map(function (item) {
            return {
              name: item.name,
              key: item.name,
              data_type: item.data_type || "string",
              default: Object.prototype.hasOwnProperty.call(item, "default") ? item.default : "",
              description: item.description || "",
              reference: item.reference || "",
            };
          });
        if (parsed.length > 0) {
          SERVICE_OPTIONS = parsed;
          rebuildServiceOptionIndex();
          repopulateServiceOptionSelect();
          renderService();
        }
      })
      .catch(function (_err) {
        // Leave only the custom option available when service definitions cannot be loaded.
      });
  }

  function initEvents() {
    window.addEventListener("resize", function () {
      Array.prototype.forEach.call(document.querySelectorAll("textarea.code-input"), function (node) {
        prepareCodeTextarea(node);
      });
    });

    el.newConfig.addEventListener("click", function () {
      state.doc = emptyDoc(state.selectedVersion, state.configType);
      state.currentFileName = "";
      state.saveFileHandle = null;
      clearOpenFileSelection();
      setCookie(LAST_FILE_COOKIE, "new-" + Date.now());
      saveDoc();
      setStatusMessage("Started a new configuration.");
      renderAll();
    });

    el.browseFile.addEventListener("click", function () {
      el.openFile.click();
    });

    el.saveConfig.addEventListener("click", function () {
      triggerConfigDownload();
    });

    el.saveAsConfig.addEventListener("click", function () {
      triggerConfigDownload(true);
    });

    el.reloadUi.addEventListener("click", function () {
      reloadUiWithCacheBust();
    });

    el.validationToggle.addEventListener("click", function () {
      state.validationCollapsed = !state.validationCollapsed;
      updateResultPanels();
    });

    el.yamlToggle.addEventListener("click", function () {
      state.yamlCollapsed = !state.yamlCollapsed;
      updateResultPanels();
    });

    el.pluginsToggle.addEventListener("click", function () {
      state.pluginsPanelCollapsed = !state.pluginsPanelCollapsed;
      updateSectionPanels();
    });

    el.labelsToggle.addEventListener("click", function () {
      state.labelsPanelCollapsed = !state.labelsPanelCollapsed;
      updateSectionPanels();
    });

    el.workersToggle.addEventListener("click", function () {
      state.workersPanelCollapsed = !state.workersPanelCollapsed;
      updateSectionPanels();
    });

    el.versionSelect.addEventListener("change", function () {
      state.selectedVersion = el.versionSelect.value;
      if (state.doc) {
        state.doc.version = state.selectedVersion;
      }
      loadCatalog(state.selectedVersion)
        .then(function () {
          return loadServiceOptions(state.selectedVersion);
        })
        .catch(function (err) {
          setValidationText(String(err));
        });
      saveDoc();
    });

    el.configTypeSelect.addEventListener("change", function () {
      state.configType = el.configTypeSelect.value;
      if (state.doc) {
        state.doc.configType = state.configType;
      }
      loadVersionsForType(state.configType)
        .then(function () {
          if (!state.selectedVersion) {
            state.catalog = null;
            state.catalogLoaded = false;
            SERVICE_OPTIONS = [];
            rebuildServiceOptionIndex();
            repopulateServiceOptionSelect();
            renderAll();
            saveDoc();
            return null;
          }
          return loadCatalog(state.selectedVersion).then(function () {
            return loadServiceOptions(state.selectedVersion);
          });
        })
        .then(function () {
          renderAll();
          saveDoc();
        })
        .catch(function (err) {
          setValidationText(String(err));
        });
    });

    el.pluginSection.addEventListener("change", function () {
      state.pluginSection = el.pluginSection.value;
      repopulatePluginNameSelect();
      updatePluginHelpState();
      updateAddPluginState();
    });

    el.pluginName.addEventListener("change", function () {
      state.pluginName = el.pluginName.value || "";
      updatePluginHelpState();
      updateAddPluginState();
    });

    el.pluginHelpToggle.addEventListener("click", function () {
      var pluginDef = selectedPluginDefinition();
      if (!pluginDef || !pluginDef.doc_url) {
        setValidationText("No linked documentation is available for the current plugin selection.");
        return;
      }
      window.open(pluginDef.doc_url, "_blank", "noopener,noreferrer");
    });

    el.addPlugin.addEventListener("click", function () {
      ensureDoc();
      if (!state.catalogLoaded || !state.catalog) {
        setValidationText("Catalog not loaded yet. Please wait and try again.");
        return;
      }
      var selectedPluginName = String(el.pluginName.value || state.pluginName || "").trim();
      if (!selectedPluginName) {
        setValidationText("Select a plugin before adding.");
        return;
      }
      var groups = pluginGroups();
      var def = groups[state.pluginSection] && groups[state.pluginSection][selectedPluginName];
      if (!def) {
        setValidationText(
          "Selected plugin is unavailable for section '" +
            state.pluginSection +
            "'. Re-select section/plugin and try again."
        );
        return;
      }
      var instance = { name: selectedPluginName };
      (def.fields || []).forEach(function (field) {
        if (field.required) {
          instance[field.name] = defaultForField(field);
        }
      });
      state.doc.config.pipeline[state.pluginSection].push(instance);
      state.pluginName = selectedPluginName;
      saveDoc();
      setValidationText("");
      renderAll();
    });

    el.addServiceField.addEventListener("click", function () {
      ensureDoc();
      var selected = selectedServiceOption();
      var key = selected ? selected.key : "";
      if (el.serviceOption.value === CUSTOM_SERVICE_OPTION) {
        key = String(el.serviceCustomKey.value || "").trim();
      }
      if (!key) {
        return;
      }

      if (selected && el.serviceOption.value !== CUSTOM_SERVICE_OPTION) {
        state.doc.config.service[key] = parseServiceValueByType(
          el.serviceValue.value,
          selected.data_type
        );
      } else {
        state.doc.config.service[key] = parseServiceValue(el.serviceValue.value);
      }

      el.serviceCustomKey.value = "";
      el.serviceValue.value = "";
      saveDoc();
      renderService();
    });

    el.serviceOption.addEventListener("change", function () {
      updateServiceOptionUI();
    });

    el.serviceHelpToggle.addEventListener("click", function () {
      var opt = selectedServiceOption();
      var isCustom = el.serviceOption.value === CUSTOM_SERVICE_OPTION;
      if (!opt || isCustom || !opt.reference) {
        setValidationText("No linked documentation is available for the current selection.");
        return;
      }
      window.open(opt.reference, "_blank", "noopener,noreferrer");
    });

    el.addLabel.addEventListener("click", function () {
      ensureDoc();
      state.doc.config.labels.push({
        name: nextLabelName(),
        pipeline: { inputs: [], filters: [], outputs: [] },
        includes: [],
      });
      saveDoc();
      renderAll();
    });

    el.addWorker.addEventListener("click", function () {
      ensureDoc();
      state.doc.config.workers.push({
        name: nextWorkerName(),
        pipeline: { inputs: [], filters: [], outputs: [] },
        labels: [],
        includes: [],
      });
      saveDoc();
      renderAll();
    });

    el.openFile.addEventListener("change", function (event) {
      var file = event.target.files && event.target.files[0];
      if (!file) {
        return;
      }
      var selectedDisplay = String(event.target.value || file.name || "").trim() || file.name;
      file
        .text()
        .then(function (text) {
          var parsedHeader = parseConfigHeader(text);
          if (/\.json$/i.test(file.name)) {
            var parsed = JSON.parse(parsedHeader.body);
            state.doc = parsed;
            ensureDoc();
            state.configType = parsedHeader.configType || parsed.configType || "fluentbit";
            state.doc.configType = state.configType;
            state.currentFileName = file.name;
            state.saveFileHandle = null;
            setOpenFileDisplay(selectedDisplay);
            el.configTypeSelect.value = state.configType;
            setCookie(LAST_FILE_COOKIE, file.name);
            return loadVersionsForType(
              state.configType,
              parsedHeader.version || parsed.version || state.selectedVersion
            )
              .then(function () {
                state.doc.version = state.selectedVersion;
                saveDoc();
                setStatusMessage("Loaded configuration file " + file.name);
                if (!state.selectedVersion) {
                  renderAll();
                  return null;
                }
                el.versionSelect.value = state.selectedVersion;
                return loadCatalog(state.selectedVersion);
              })
              .then(function () {
                if (!state.selectedVersion) {
                  return null;
                }
                return loadServiceOptions(state.selectedVersion);
              })
              .then(renderAll);
          }

          if (/\.ya?ml$/i.test(file.name)) {
            state.configType = "fluentbit";
            el.configTypeSelect.value = state.configType;
            return loadVersionsForType(state.configType, parsedHeader.version || state.selectedVersion)
              .then(function () {
                return fetchJson(API_BASE + "/parse/fluentbit/" + encodeURIComponent(state.selectedVersion), {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ text: parsedHeader.body }),
                });
              })
              .then(function (result) {
                state.doc = {
                  version: state.selectedVersion,
                  configType: "fluentbit",
                  config: result.config || emptyDoc(state.selectedVersion, "fluentbit").config,
                  annotations: {},
                };
                ensureDoc();
                state.currentFileName = file.name;
                state.saveFileHandle = null;
                setOpenFileDisplay(selectedDisplay);
                setCookie(LAST_FILE_COOKIE, file.name);
                saveDoc();
                if (Array.isArray(result.errors) && result.errors.length > 0) {
                  setStatusMessage("There were problems loading configuration file " + file.name + ". Recognized sections were loaded.");
                  renderValidationState({ ok: false, errors: result.errors });
                } else {
                  setStatusMessage("Loaded configuration file " + file.name);
                  renderValidationState(null);
                }
                return loadCatalog(state.selectedVersion);
              })
              .then(function () {
                return loadServiceOptions(state.selectedVersion);
              })
              .then(renderAll);
          }

          state.configType = parsedHeader.configType || "fluentd";
          el.configTypeSelect.value = state.configType;
          state.currentFileName = file.name;
          state.saveFileHandle = null;
          setOpenFileDisplay(selectedDisplay);
          setCookie(LAST_FILE_COOKIE, file.name);
          return loadVersionsForType(state.configType, parsedHeader.version || state.selectedVersion)
            .then(function () {
              return fetchJson(API_BASE + "/parse/fluentd/" + encodeURIComponent(state.selectedVersion), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: parsedHeader.body }),
              });
            })
            .then(function (result) {
              state.doc = {
                version: state.selectedVersion,
                configType: "fluentd",
                config: result.config || emptyDoc(state.selectedVersion, "fluentd").config,
                annotations: {},
              };
              ensureDoc();
              saveDoc();
              setStatusMessage("Loaded configuration file " + file.name);
              return loadCatalog(state.selectedVersion);
            })
            .then(function () {
              return loadServiceOptions(state.selectedVersion);
            })
            .then(renderAll);
        })
        .catch(function (err) {
          if (err && err.payload && Array.isArray(err.payload.errors)) {
            renderValidationState({ ok: false, errors: err.payload.errors });
            setStatusMessage("There were problems loading configuration file " + file.name + ".");
            return;
          }
          setValidationText(String(err));
          setStatusMessage("There were problems loading configuration file " + file.name + ".");
        });
    });

    el.validateBtn.addEventListener("click", function () {
      if (!state.doc) {
        return;
      }
      var payload = {
        config: state.doc.config,
        annotations: state.doc.annotations || {},
        profile: "strict",
      };
      fetchJson(API_BASE + "/validate/" + encodeURIComponent(state.doc.version) + currentApiQuery(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (result) {
          renderValidationState(result);
        })
        .catch(function (err) {
          setValidationText(String(err));
        });
    });

    el.renderBtn.addEventListener("click", function () {
      if (!state.doc) {
        setStatusMessage("Load or create a configuration before rendering.");
        return;
      }
      var payload = {
        config: state.doc.config,
        annotations: state.doc.annotations || {},
        include_comments: true,
      };
      var endpoint = state.configType === "fluentd"
        ? API_BASE + "/render/fluentd/" + encodeURIComponent(state.doc.version)
        : API_BASE + "/render/yaml/" + encodeURIComponent(state.doc.version) + currentApiQuery();
      state.yamlCollapsed = false;
      updateResultPanels();
      fetchJson(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (result) {
          setStatusMessage("Rendered configuration updated.");
          setYamlText(result.yaml || result.text || "", true);
        })
        .catch(function (err) {
          setStatusMessage("Rendering failed.");
          setYamlText(String(err));
        });
    });
  }

  function init() {
    installGlobalUiErrorHandlers();
    applyCssOverrides();
    repopulateServiceOptionSelect();
    updateAddPluginState();
    renderValidationState(null);
    setYamlText("");
    updateResultPanels();
    updateSectionPanels();
    initEvents();

    fetchJson(API_BASE + "/health")
      .then(function (health) {
        state.readOnly = Boolean(health.read_only);
        updateReadOnlyState();
        if (health.app_enable_dev_features) {
          el.reloadUi.classList.remove("hidden");
        }
      })
      .catch(function (err) {
        state.catalogLoaded = false;
        updateAddPluginState();
        setValidationText(String(err));
      });

    fetchJson(API_BASE + "/issue-codes")
      .then(function (payload) {
        state.issueCodeMap = (payload && payload.codes) || {};
      })
      .catch(function (_err) {
        state.issueCodeMap = {};
      });

    loadVersionsForType(state.configType)
      .then(function () {
        var cookieDoc = localStorage.getItem(LAST_DOC_STORAGE);
        var cookieName = getCookie(LAST_FILE_COOKIE);
        if (cookieDoc && cookieName) {
          try {
            var parsed = JSON.parse(cookieDoc);
            state.doc = parsed;
            state.configType = parsed.configType || "fluentbit";
            state.currentFileName = cookieName;
            setOpenFileDisplay(/^new-\d+$/i.test(cookieName) ? "" : cookieName);
          } catch (_e) {
            clearCookie(LAST_FILE_COOKIE);
            localStorage.removeItem(LAST_DOC_STORAGE);
          }
        }

        if (!state.doc) {
          state.doc = emptyDoc(state.selectedVersion, state.configType);
        }

        ensureDoc();
        state.doc.configType = state.configType;
        el.configTypeSelect.value = state.configType;
        return loadVersionsForType(state.configType, state.doc.version || state.selectedVersion);
      })
      .then(function () {
        if (!state.selectedVersion) {
          renderAll();
          return null;
        }
        return loadCatalog(state.selectedVersion).then(function () {
          return loadServiceOptions(state.selectedVersion);
        });
      })
      .then(function () {
        renderAll();
        updateReadOnlyState();
        updateRenderedDirtyState();
      })
      .catch(function (err) {
        setValidationText(String(err));
      });
  }

  init();
})();
