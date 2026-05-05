import { CatalogPayload, VersionsResponse } from '../types/catalog';

const API_BASE = '/config-service/api/v1';

export interface HealthResponse {
  ok: boolean;
  mode: 'standalone' | 'embedded' | string;
  app_enable_dev_features: boolean;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchVersions(): Promise<VersionsResponse> {
  return json<VersionsResponse>(await fetch(`${API_BASE}/versions`));
}

export async function fetchHealth(): Promise<HealthResponse> {
  return json<HealthResponse>(await fetch(`${API_BASE}/health`));
}

export async function fetchCatalog(version: string): Promise<CatalogPayload> {
  return json<CatalogPayload>(await fetch(`${API_BASE}/catalog/${version}`));
}

export async function validateConfig(version: string, payload: unknown): Promise<unknown> {
  return json<unknown>(
    await fetch(`${API_BASE}/validate/${version}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  );
}

export async function renderYaml(version: string, payload: unknown): Promise<{ ok: boolean; yaml: string }> {
  return json<{ ok: boolean; yaml: string }>(
    await fetch(`${API_BASE}/render/yaml/${version}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
  );
}
