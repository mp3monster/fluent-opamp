import { ChangeEvent, useEffect, useMemo, useState } from 'react';

import { fetchCatalog, fetchVersions, renderYaml, validateConfig } from './api/client';
import { PluginCard } from './components/PluginCard';
import { CatalogPayload, PluginDefinition, PluginSection } from './types/catalog';
import { DesignDoc, PluginInstance } from './types/config';
import { clearCookie, getCookie, setCookie } from './utils/cookies';
import { defaultForField, requiredFieldNames } from './utils/schema';

import './app.css';

const LAST_FILE_COOKIE = 'config_service_last_opened_name';
const LAST_DOC_STORAGE = 'config_service_last_opened_doc';

function emptyDoc(version: string, configType: 'fluentbit' | 'fluentd'): DesignDoc {
  return {
    version,
    configType,
    config: {
      pipeline: {
        inputs: [],
        filters: [],
        outputs: []
      }
    },
    annotations: {}
  };
}

function buildRequiredDefaults(plugin: PluginDefinition): Record<string, unknown> {
  const base: Record<string, unknown> = {};
  for (const field of plugin.fields) {
    if (field.required) {
      base[field.name] = defaultForField(field);
    }
  }
  return base;
}

function pluginGroups(catalog: CatalogPayload | null): Record<PluginSection, Record<string, PluginDefinition>> {
  return catalog?.plugins?.fluentbit ?? { inputs: {}, filters: {}, outputs: {} };
}

export default function App(): JSX.Element {
  const [versions, setVersions] = useState<string[]>([]);
  const [selectedVersion, setSelectedVersion] = useState('');
  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [configType, setConfigType] = useState<'fluentbit' | 'fluentd'>('fluentbit');
  const [doc, setDoc] = useState<DesignDoc | null>(null);
  const [yamlPreview, setYamlPreview] = useState('');
  const [validationOutput, setValidationOutput] = useState('');
  const [pluginSection, setPluginSection] = useState<PluginSection>('inputs');
  const [pluginName, setPluginName] = useState('');
  const [collapseState, setCollapseState] = useState<Record<string, boolean>>({});
  const groups = useMemo(() => pluginGroups(catalog), [catalog]);
  const pluginNames = useMemo(() => Object.keys(groups[pluginSection] ?? {}), [groups, pluginSection]);

  useEffect(() => {
    (async () => {
      const versionsResp = await fetchVersions();
      setVersions(versionsResp.versions);
      const cookieDoc = localStorage.getItem(LAST_DOC_STORAGE);
      const cookieName = getCookie(LAST_FILE_COOKIE);
      const version = versionsResp.default;
      setSelectedVersion(version);
      if (cookieName && cookieDoc) {
        try {
          const parsed = JSON.parse(cookieDoc) as DesignDoc;
          setDoc(parsed);
          setSelectedVersion(parsed.version || version);
          setConfigType(parsed.configType || 'fluentbit');
          return;
        } catch {
          clearCookie(LAST_FILE_COOKIE);
          localStorage.removeItem(LAST_DOC_STORAGE);
        }
      }
      setDoc(emptyDoc(version, 'fluentbit'));
    })().catch((error: unknown) => {
      setValidationOutput(String(error));
    });
  }, []);

  useEffect(() => {
    if (!selectedVersion) {
      return;
    }
    fetchCatalog(selectedVersion)
      .then((payload) => {
        setCatalog(payload);
        if (!pluginName) {
          const first = Object.keys(payload.plugins.inputs)[0] ?? '';
          setPluginName(first);
        }
      })
      .catch((error: unknown) => setValidationOutput(String(error)));
  }, [selectedVersion]);

  useEffect(() => {
    if (!doc) {
      return;
    }
    localStorage.setItem(LAST_DOC_STORAGE, JSON.stringify(doc));
  }, [doc]);

  const updatePlugin = (section: PluginSection, idx: number, value: PluginInstance) => {
    if (!doc) {
      return;
    }
    const next = structuredClone(doc);
    next.config.pipeline[section][idx] = value;
    setDoc(next);
  };

  const movePlugin = (section: PluginSection, idx: number, direction: -1 | 1) => {
    if (!doc) {
      return;
    }
    const target = idx + direction;
    const list = [...doc.config.pipeline[section]];
    if (target < 0 || target >= list.length) {
      return;
    }
    [list[idx], list[target]] = [list[target], list[idx]];
    setDoc({ ...doc, config: { ...doc.config, pipeline: { ...doc.config.pipeline, [section]: list } } });
  };

  const removePlugin = (section: PluginSection, idx: number) => {
    if (!doc) {
      return;
    }
    const list = [...doc.config.pipeline[section]];
    list.splice(idx, 1);
    setDoc({ ...doc, config: { ...doc.config, pipeline: { ...doc.config.pipeline, [section]: list } } });
  };

  const toggleCollapse = (section: PluginSection, idx: number) => {
    const key = `${section}-${idx}`;
    setCollapseState((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const addPlugin = () => {
    if (!doc || !catalog || !pluginName) {
      return;
    }
    const definition = groups[pluginSection][pluginName];
    if (!definition) {
      return;
    }
    const requiredNames = requiredFieldNames(definition);
    const requiredDefaults = buildRequiredDefaults(definition);
    const instance: PluginInstance = {
      name: pluginName,
      ...requiredDefaults
    };
    // Ensure required fields exist even when default value is undefined.
    for (const requiredName of requiredNames) {
      if (!(requiredName in instance)) {
        instance[requiredName] = '';
      }
    }

    const next = structuredClone(doc);
    next.config.pipeline[pluginSection].push(instance);
    setDoc(next);
  };

  const createNewConfig = () => {
    const next = emptyDoc(selectedVersion, configType);
    setDoc(next);
    setCookie(LAST_FILE_COOKIE, `new-${Date.now()}`);
  };

  const onOpenFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const text = await file.text();
    const parsed = JSON.parse(text) as DesignDoc;
    setDoc(parsed);
    setSelectedVersion(parsed.version);
    setConfigType(parsed.configType);
    setCookie(LAST_FILE_COOKIE, file.name);
    localStorage.setItem(LAST_DOC_STORAGE, JSON.stringify(parsed));
  };

  const runValidate = async () => {
    if (!doc) {
      return;
    }
    const payload = {
      config: doc.config,
      annotations: doc.annotations,
      profile: 'strict'
    };
    try {
      const result = await validateConfig(doc.version, payload);
      setValidationOutput(JSON.stringify(result, null, 2));
    } catch (error) {
      setValidationOutput(String(error));
    }
  };

  const runRender = async () => {
    if (!doc) {
      return;
    }
    const payload = {
      config: doc.config,
      annotations: doc.annotations,
      include_comments: true
    };
    try {
      const result = await renderYaml(doc.version, payload);
      setYamlPreview(result.yaml);
    } catch (error) {
      setYamlPreview(String(error));
    }
  };

  return (
    <div className="page-shell">
      <header>
        <h1>Config Service</h1>
        <p>Schema-driven Fluent Bit/Fluentd configuration editor</p>
      </header>

      <section className="toolbar">
        <label>
          Open configuration file
          <input type="file" accept="application/json" onChange={onOpenFile} />
        </label>

        <button type="button" onClick={createNewConfig}>
          New Configuration
        </button>

        <label>
          Version
          <select
            value={selectedVersion}
            onChange={(event) => {
              setSelectedVersion(event.target.value);
              setDoc((current) =>
                current ? { ...current, version: event.target.value } : emptyDoc(event.target.value, configType)
              );
            }}
          >
            {versions.map((version) => (
              <option key={version} value={version}>
                {version}
              </option>
            ))}
          </select>
        </label>

        <label>
          Configuration Type
          <select
            value={configType}
            onChange={(event) => {
              const value = event.target.value as 'fluentbit' | 'fluentd';
              setConfigType(value);
              setDoc((current) => (current ? { ...current, configType: value } : current));
            }}
          >
            <option value="fluentbit">Fluent Bit</option>
            <option value="fluentd">Fluentd</option>
          </select>
        </label>
      </section>

      <section className="plugin-adder">
        <h2>Add Plugin</h2>
        <label>
          Section
          <select
            value={pluginSection}
            onChange={(event) => {
              const nextSection = event.target.value as PluginSection;
              setPluginSection(nextSection);
              const nextName = Object.keys(groups[nextSection] ?? {})[0] ?? '';
              setPluginName(nextName);
            }}
          >
            <option value="inputs">Inputs</option>
            <option value="filters">Filters</option>
            <option value="outputs">Outputs</option>
          </select>
        </label>
        <label>
          Plugin
          <select value={pluginName} onChange={(event) => setPluginName(event.target.value)}>
            {pluginNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={addPlugin}>
          Add Plugin
        </button>
      </section>

      <section className="pipeline-grid">
        {(['inputs', 'filters', 'outputs'] as PluginSection[]).map((section) => (
          <article key={section}>
            <h2>{section}</h2>
            {(doc?.config.pipeline[section] ?? []).map((instance, index) => {
              const def = groups[section][instance.name];
              if (!def) {
                return null;
              }
              return (
                <PluginCard
                  key={`${section}-${index}-${instance.name}`}
                  section={section}
                  index={index}
                  pluginName={instance.name}
                  pluginDef={def}
                  value={instance}
                  collapsed={Boolean(collapseState[`${section}-${index}`])}
                  onToggleCollapse={() => toggleCollapse(section, index)}
                  onChange={(value) => updatePlugin(section, index, value)}
                  onRemove={() => removePlugin(section, index)}
                  onMoveUp={() => movePlugin(section, index, -1)}
                  onMoveDown={() => movePlugin(section, index, 1)}
                />
              );
            })}
          </article>
        ))}
      </section>

      <section className="actions">
        <button type="button" onClick={runValidate}>
          Validate
        </button>
        <button type="button" onClick={runRender}>
          Render YAML
        </button>
      </section>

      <section className="results">
        <div>
          <h3>Validation</h3>
          <pre>{validationOutput}</pre>
        </div>
        <div>
          <h3>YAML Preview</h3>
          <pre>{yamlPreview}</pre>
        </div>
      </section>
    </div>
  );
}
