import { PluginSection } from './catalog';

export interface PluginInstance {
  name: string;
  [key: string]: unknown;
}

export interface PipelineConfig {
  inputs: PluginInstance[];
  filters: PluginInstance[];
  outputs: PluginInstance[];
}

export interface DesignDoc {
  version: string;
  configType: 'fluentbit' | 'fluentd';
  config: {
    pipeline: PipelineConfig;
  };
  annotations: Record<string, string>;
}

export interface PluginPicker {
  section: PluginSection;
  pluginName: string;
}
