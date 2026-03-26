/** Simple fetch wrapper for the Gaia LKM API. */

const BASE = '/api';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getHealth() {
  return fetchJson<{ status: string }>('/health');
}

// -- Table Browser --

export async function getTableList() {
  return fetchJson<{ tables: string[] }>('/tables');
}

export async function getTableData(name: string, limit = 100) {
  return fetchJson<{
    table: string;
    columns: string[];
    rows: Record<string, unknown>[];
    total: number;
  }>(`/tables/${encodeURIComponent(name)}?limit=${limit}`);
}

// -- Neo4j Stats --

export async function getNeo4jStats() {
  return fetchJson<{
    knowledge_nodes: number;
    factor_nodes: number;
    edges: number;
    available: boolean;
  }>('/neo4j/stats');
}

// -- Graph --

export async function getGraph(scope: 'global' | 'local', packageId?: string) {
  let url = `/graph?scope=${scope}`;
  if (scope === 'local' && packageId) {
    url += `&package_id=${encodeURIComponent(packageId)}`;
  }
  return fetchJson<{
    nodes: Array<{
      id: string;
      label: string;
      type: string;
      reasoning_type?: string;
      belief?: number;
      prior?: number;
    }>;
    edges: Array<{ from: string; to: string; role: string }>;
    packages?: string[];
  }>(url);
}
