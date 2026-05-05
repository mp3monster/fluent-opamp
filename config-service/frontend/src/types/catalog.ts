export type PluginSection = 'inputs' | 'filters' | 'outputs';

export interface CatalogField {
  name: string;
  required: boolean;
  description: string;
  reference: string;
  data_type: string;
  validation_rule?: Record<string, unknown>;
  default?: unknown;
}

export interface PluginDefinition {
  title?: string;
  description?: string;
  doc_url?: string;
  fields: CatalogField[];
}

export interface CatalogPayload {
  fluent_bit_version: string;
  plugins: {
    fluentbit: {
      inputs: Record<string, PluginDefinition>;
      filters: Record<string, PluginDefinition>;
      outputs: Record<string, PluginDefinition>;
    };
  };
}

export interface VersionsResponse {
  versions: string[];
  default: string;
}
