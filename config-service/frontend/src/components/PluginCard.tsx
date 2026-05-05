import { useMemo } from 'react';
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';

import { PluginDefinition } from '../types/catalog';
import { PluginInstance } from '../types/config';
import { buildPluginSchema, defaultForField } from '../utils/schema';

interface PluginCardProps {
  section: 'inputs' | 'filters' | 'outputs';
  index: number;
  pluginName: string;
  pluginDef: PluginDefinition;
  value: PluginInstance;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onChange: (value: PluginInstance) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

export function PluginCard(props: PluginCardProps): JSX.Element {
  const optionalMissing = useMemo(
    () => props.pluginDef.fields.filter((field) => !field.required && !(field.name in props.value)),
    [props.pluginDef.fields, props.value]
  );

  const optionalPresent = useMemo(
    () => props.pluginDef.fields.filter((field) => !field.required && field.name in props.value),
    [props.pluginDef.fields, props.value]
  );

  const schema = useMemo(
    () => buildPluginSchema(props.pluginName, props.pluginDef, props.value),
    [props.pluginDef, props.pluginName, props.value]
  );

  const summary = `${props.section}[${props.index}] ${props.pluginName}`;

  return (
    <div className="plugin-card">
      <div className="plugin-card-header">
        <button type="button" onClick={props.onToggleCollapse}>
          {props.collapsed ? 'Expand' : 'Collapse'}
        </button>
        <strong>{summary}</strong>
        <div className="plugin-card-actions">
          <button type="button" onClick={props.onMoveUp}>
            Up
          </button>
          <button type="button" onClick={props.onMoveDown}>
            Down
          </button>
          <button type="button" onClick={props.onRemove}>
            Remove
          </button>
        </div>
      </div>

      {!props.collapsed ? (
        <>
          <Form
            schema={schema}
            validator={validator}
            formData={props.value}
            onChange={(event) => props.onChange((event.formData ?? {}) as PluginInstance)}
            onSubmit={(event) => props.onChange((event.formData ?? {}) as PluginInstance)}
          >
            <></>
          </Form>

          <div className="optional-fields">
            <label htmlFor={`optional-${props.section}-${props.index}`}>Add Optional Attribute</label>
            <select id={`optional-${props.section}-${props.index}`} defaultValue="">
              <option value="">Select attribute...</option>
              {optionalMissing.map((field) => (
                <option key={field.name} value={field.name}>
                  {field.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                const select = document.getElementById(
                  `optional-${props.section}-${props.index}`
                ) as HTMLSelectElement | null;
                if (!select || !select.value) {
                  return;
                }
                const field = props.pluginDef.fields.find((item) => item.name === select.value);
                if (!field) {
                  return;
                }
                props.onChange({ ...props.value, [field.name]: defaultForField(field) });
                select.value = '';
              }}
            >
              Add
            </button>
          </div>

          {optionalPresent.length > 0 ? (
            <div className="optional-present">
              <span>Optional attributes added:</span>
              <ul>
                {optionalPresent.map((field) => (
                  <li key={field.name}>
                    <code>{field.name}</code>
                    <button
                      type="button"
                      onClick={() => {
                        const next = { ...props.value };
                        delete next[field.name];
                        props.onChange(next);
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
