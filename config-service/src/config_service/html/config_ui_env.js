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

  function create(deps) {
    var state = deps.state;
    var el = deps.el;
    var saveDoc = deps.saveDoc;
    var ensureDoc = deps.ensureDoc;
    var isReadOnlyMode = deps.isReadOnlyMode;
    var parseServiceValue = deps.parseServiceValue;

    var METADATA_PREFIX = "_metadata.";
    var DEFAULT_METADATA_OPTION_FLUENT_BIT_VERSION = "fluent_bit_version";
    var DEFAULT_METADATA_OPTION_CONFIGURATION_DATE = "configuration_date";
    var DEFAULT_METADATA_OPTION_CONFIGURATION_VERSION = "config_version";

    function envEntries() {
      return Object.entries((state.doc && state.doc.config && state.doc.config.env) || {});
    }

    function isMetadataEnvKey(key) {
      return String(key || "").indexOf(METADATA_PREFIX) === 0;
    }

    function normalizeMetadataKeyInput(rawKey) {
      var key = String(rawKey || "").trim();
      if (!key) {
        return "";
      }
      key = key.replace(/^_+\.?metadata\./i, "");
      key = key.replace(/^metadata\./i, "");
      key = key.replace(/^\.+/, "");
      key = key.replace(/^_+\.+/, "");
      return key.trim();
    }

    function toMetadataStorageKey(rawKey) {
      var key = normalizeMetadataKeyInput(rawKey);
      if (!key) {
        return "";
      }
      return METADATA_PREFIX + key;
    }

    function metadataDisplayKey(storageKey) {
      return String(storageKey || "").replace(/^_metadata\./i, "");
    }

    function renderNormalEnv() {
      if (!el.envList) {
        return;
      }
      el.envList.innerHTML = "";
      var entries = envEntries().filter(function (entry) {
        return entry[0] !== "_meta" && !isMetadataEnvKey(entry[0]);
      });

      if (entries.length === 0) {
        var empty = document.createElement("p");
        empty.textContent = "No environment variables configured.";
        el.envList.appendChild(empty);
        return;
      }

      var card = document.createElement("div");
      card.className = "plugin-card service-card";
      var body = document.createElement("div");
      body.className = "field-grid";

      entries.forEach(function (entry) {
        var key = entry[0];
        var value = entry[1];
        var row = document.createElement("div");
        row.className = "service-row";

        var keyInput = document.createElement("input");
        keyInput.value = key;
        keyInput.disabled = isReadOnlyMode();
        keyInput.addEventListener("change", function () {
          var newKey = String(keyInput.value || "").trim();
          if (!newKey || newKey === key) {
            keyInput.value = key;
            return;
          }
          state.doc.config.env[newKey] = state.doc.config.env[key];
          delete state.doc.config.env[key];
          saveDoc();
          renderEnv();
        });
        row.appendChild(keyInput);

        var valueInput = document.createElement("input");
        valueInput.value = String(value === undefined || value === null ? "" : value);
        valueInput.disabled = isReadOnlyMode();
        valueInput.addEventListener("change", function () {
          state.doc.config.env[key] = parseServiceValue(valueInput.value);
          saveDoc();
        });
        row.appendChild(valueInput);

        var removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.textContent = "-";
        removeBtn.className = "icon-remove right-align";
        removeBtn.title = "Remove environment variable";
        removeBtn.disabled = isReadOnlyMode();
        removeBtn.addEventListener("click", function () {
          delete state.doc.config.env[key];
          saveDoc();
          renderEnv();
        });
        row.appendChild(removeBtn);

        body.appendChild(row);
      });

      card.appendChild(body);
      el.envList.appendChild(card);
    }

    function metadataPresetForKey(rawKey) {
      var key = normalizeMetadataKeyInput(rawKey);
      var selectedVersion = String((state.doc && state.doc.version) || state.selectedVersion || "").trim();
      var today = new Date().toISOString().slice(0, 10);
      if (key === DEFAULT_METADATA_OPTION_FLUENT_BIT_VERSION) {
        return {
          key: key,
          defaultValue: selectedVersion,
          valueOptions: Array.isArray(state.versions) ? state.versions.map(String) : [],
        };
      }
      if (key === DEFAULT_METADATA_OPTION_CONFIGURATION_DATE) {
        return {
          key: key,
          defaultValue: today,
          valueOptions: [today],
        };
      }
      if (key === DEFAULT_METADATA_OPTION_CONFIGURATION_VERSION) {
        return {
          key: key,
          defaultValue: selectedVersion,
          valueOptions: selectedVersion ? [selectedVersion] : [],
        };
      }
      return null;
    }

    function renderMetadataValueOptions(rawKey) {
      if (!el.metadataEnvValueOptions) {
        return;
      }
      el.metadataEnvValueOptions.innerHTML = "";
      var preset = metadataPresetForKey(rawKey);
      if (!preset || !Array.isArray(preset.valueOptions)) {
        return;
      }
      preset.valueOptions.forEach(function (optionValue) {
        if (optionValue === undefined || optionValue === null || String(optionValue).trim() === "") {
          return;
        }
        var option = document.createElement("option");
        option.value = String(optionValue);
        el.metadataEnvValueOptions.appendChild(option);
      });
    }

    function applyMetadataPresetSuggestion() {
      var key = String((el.metadataEnvKeyInput && el.metadataEnvKeyInput.value) || "").trim();
      var preset = metadataPresetForKey(key);
      renderMetadataValueOptions(key);
      if (!preset || !el.metadataEnvValueInput) {
        return;
      }
      var currentValue = String(el.metadataEnvValueInput.value || "").trim();
      if (!currentValue || currentValue === preset.defaultValue) {
        el.metadataEnvValueInput.value = String(preset.defaultValue || "");
      }
    }

    function renderMetadataEnv() {
      if (!el.metadataEnvList) {
        return;
      }
      el.metadataEnvList.innerHTML = "";
      renderMetadataValueOptions((el.metadataEnvKeyInput && el.metadataEnvKeyInput.value) || "");

      var entries = envEntries().filter(function (entry) {
        return isMetadataEnvKey(entry[0]);
      });

      if (entries.length === 0) {
        var empty = document.createElement("p");
        empty.textContent = "No metadata environment variables configured.";
        el.metadataEnvList.appendChild(empty);
        return;
      }

      var card = document.createElement("div");
      card.className = "plugin-card service-card";
      var body = document.createElement("div");
      body.className = "field-grid";

      entries.forEach(function (entry) {
        var key = entry[0];
        var value = entry[1];
        var row = document.createElement("div");
        row.className = "service-row";

        var keyInput = document.createElement("input");
        keyInput.value = metadataDisplayKey(key);
        keyInput.disabled = isReadOnlyMode();
        keyInput.addEventListener("change", function () {
          var newStorageKey = toMetadataStorageKey(keyInput.value);
          if (!newStorageKey || newStorageKey === key) {
            keyInput.value = metadataDisplayKey(key);
            return;
          }
          state.doc.config.env[newStorageKey] = state.doc.config.env[key];
          delete state.doc.config.env[key];
          saveDoc();
          renderEnv();
        });
        row.appendChild(keyInput);

        var valueInput = document.createElement("input");
        valueInput.value = String(value === undefined || value === null ? "" : value);
        valueInput.disabled = isReadOnlyMode();
        valueInput.addEventListener("change", function () {
          state.doc.config.env[key] = parseServiceValue(valueInput.value);
          saveDoc();
        });
        row.appendChild(valueInput);

        var removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.textContent = "-";
        removeBtn.className = "icon-remove right-align";
        removeBtn.title = "Remove metadata variable";
        removeBtn.disabled = isReadOnlyMode();
        removeBtn.addEventListener("click", function () {
          delete state.doc.config.env[key];
          saveDoc();
          renderEnv();
        });
        row.appendChild(removeBtn);

        body.appendChild(row);
      });

      card.appendChild(body);
      el.metadataEnvList.appendChild(card);
    }

    function addMetadataField(rawKey, rawValue) {
      ensureDoc();
      var storageKey = toMetadataStorageKey(rawKey);
      if (!storageKey) {
        return;
      }
      state.doc.config.env[storageKey] = parseServiceValue(rawValue || "");
      saveDoc();
      renderEnv();
    }

    function bindEvents() {
      if (el.addEnvField && el.addEnvField.dataset.boundEnvHandler !== "true") {
        el.addEnvField.addEventListener("click", function () {
          ensureDoc();
          var key = String((el.envKeyInput && el.envKeyInput.value) || "").trim();
          if (!key) {
            return;
          }
          state.doc.config.env[key] = parseServiceValue((el.envValueInput && el.envValueInput.value) || "");
          if (el.envKeyInput) {
            el.envKeyInput.value = "";
          }
          if (el.envValueInput) {
            el.envValueInput.value = "";
          }
          saveDoc();
          renderEnv();
        });
        el.addEnvField.dataset.boundEnvHandler = "true";
      }

      if (el.addMetadataEnvField && el.addMetadataEnvField.dataset.boundMetadataEnvHandler !== "true") {
        el.addMetadataEnvField.addEventListener("click", function () {
          var normalizedKey = normalizeMetadataKeyInput((el.metadataEnvKeyInput && el.metadataEnvKeyInput.value) || "");
          var preset = metadataPresetForKey(normalizedKey);
          var rawValue = (el.metadataEnvValueInput && el.metadataEnvValueInput.value) || "";
          if (preset && String(rawValue || "").trim() === "") {
            rawValue = preset.defaultValue || "";
          }
          addMetadataField(
            normalizedKey,
            rawValue
          );
          if (el.metadataEnvKeyInput) {
            el.metadataEnvKeyInput.value = "";
          }
          if (el.metadataEnvValueInput) {
            el.metadataEnvValueInput.value = "";
          }
          renderMetadataValueOptions("");
        });
        el.addMetadataEnvField.dataset.boundMetadataEnvHandler = "true";
      }

      if (el.metadataEnvKeyInput && el.metadataEnvKeyInput.dataset.boundMetadataKeyHandler !== "true") {
        el.metadataEnvKeyInput.addEventListener("input", applyMetadataPresetSuggestion);
        el.metadataEnvKeyInput.addEventListener("change", applyMetadataPresetSuggestion);
        el.metadataEnvKeyInput.dataset.boundMetadataKeyHandler = "true";
      }
    }

    function renderEnv() {
      ensureDoc();
      renderNormalEnv();
      renderMetadataEnv();
    }

    return {
      renderEnv: renderEnv,
      bindEvents: bindEvents,
    };
  }

  global.ConfigServiceUiEnv = {
    create: create,
  };
})(window);
