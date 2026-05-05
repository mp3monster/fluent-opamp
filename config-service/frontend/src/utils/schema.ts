import { RJSFSchema } from '@rjsf/utils';
import { CatalogField, PluginDefinition } from '../types/catalog';
import { PluginInstance } from '../types/config';

function mapType(dataType: string): string {
  switch (dataType.toLowerCase()) {
    case 'integer':
      return 'integer';
    case 'float':
    case 'number':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'array':
    case 'list':
      return 'array';
    case 'map':
    case 'object':
      return 'object';
    default:
      return 'string';
  }
}

export function defaultForField(field: CatalogField): unknown {
  if (field.default !== undefined) {
    return field.default;
  }
  switch (mapType(field.data_type)) {
    case 'integer':
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'array':
      return [];
    case 'object':
      return {};
    default:
      return '';
  }
}

export function requiredFieldNames(plugin: PluginDefinition): string[] {
  return plugin.fields.filter((field) => field.required).map((field) => field.name);
}

export function buildPluginSchema(
  pluginName: string,
  plugin: PluginDefinition,
  instance: PluginInstance
): RJSFSchema {
  const properties: Record<string, RJSFSchema> = {
    name: {
      type: 'string',
      title: 'Plugin',
      const: pluginName,
      default: pluginName,
      readOnly: true
    }
  };

  const required: string[] = ['name'];
  const existingKeys = new Set(Object.keys(instance));

  for (const field of plugin.fields) {
    if (!field.required && !existingKeys.has(field.name)) {
      continue;
    }
    properties[field.name] = {
      type: mapType(field.data_type),
      title: field.name,
      description: `${field.description} (${field.reference})`,
      default: field.default
    };
    if (field.required) {
      required.push(field.name);
    }
  }

  return {
    type: 'object',
    properties,
    required,
    additionalProperties: false
  };
}
