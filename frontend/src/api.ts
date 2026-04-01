const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export interface Stats {
  [table: string]: number;
}

export interface LocalMember {
  local_id: string;
  package_id: string;
  version: string;
}

export interface Variable {
  id: string;
  type: string;
  visibility: string;
  content: string | null;
  content_hash: string;
  parameters: { name: string; type: string }[];
  local_members: LocalMember[];
  representative_lcn: LocalMember;
}

export interface VariableDetail extends Variable {
  connected_factors: ConnectedFactor[];
  bindings: Binding[];
}

export interface ConnectedFactor {
  id: string;
  factor_type: string;
  subtype: string;
  premises: string[];
  conclusion: string;
  steps: { reasoning: string }[] | null;
  role: string;
}

export interface Factor {
  id: string;
  factor_type: string;
  subtype: string;
  premises: string[];
  conclusion: string;
  source_package: string;
  steps: { reasoning: string }[] | null;
}

export interface FactorDetail {
  id: string;
  factor_type: string;
  subtype: string;
  premises: { id: string; type?: string; content: string | null }[];
  conclusion: { id: string; type?: string; content: string | null };
  source_package: string;
  steps: { reasoning: string }[] | null;
}

export interface Binding {
  local_id: string;
  global_id: string;
  binding_type: string;
  package_id: string;
  version: string;
  decision: string;
  reason: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  type: "variable" | "factor";
  subtype: string;
  visibility?: string;
  content?: string | null;
  factor_type?: string;
  local_members_count?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: "premise" | "conclusion";
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  stats: () => get<Stats>("/stats"),
  variables: (params?: { type?: string; visibility?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.type) q.set("type", params.type);
    if (params?.visibility) q.set("visibility", params.visibility);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return get<Variable[]>(`/variables${qs ? `?${qs}` : ""}`);
  },
  variable: (id: string) => get<VariableDetail>(`/variables/${encodeURIComponent(id)}`),
  factors: (params?: { factor_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.factor_type) q.set("factor_type", params.factor_type);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return get<Factor[]>(`/factors${qs ? `?${qs}` : ""}`);
  },
  factor: (id: string) => get<FactorDetail>(`/factors/${encodeURIComponent(id)}`),
  bindings: (params?: { package_id?: string; binding_type?: string }) => {
    const q = new URLSearchParams();
    if (params?.package_id) q.set("package_id", params.package_id);
    if (params?.binding_type) q.set("binding_type", params.binding_type);
    const qs = q.toString();
    return get<Binding[]>(`/bindings${qs ? `?${qs}` : ""}`);
  },
  graph: () => get<GraphData>("/graph"),
};
