export interface Node {
  id: number;
  type: string;
  subtype: string | null;
  title: string | null;
  content: string | Record<string, unknown> | unknown[];
  keywords: string[];
  prior: number;
  belief: number | null;
  status: "active" | "deleted";
  metadata: Record<string, unknown>;
  extra: Record<string, unknown>;
  created_at: string | null;
}

export interface HyperEdge {
  id: number;
  type: string;
  subtype: string | null;
  premises: number[];
  conclusions: number[];
  probability: number | null;
  verified: boolean;
  reasoning: unknown[];
  metadata: Record<string, unknown>;
  extra: Record<string, unknown>;
  created_at: string | null;
}

export interface SubgraphResponse {
  nodes: Node[];
  edges: HyperEdge[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface TextSearchResult {
  node: Node;
  score: number;
}

export interface StatsResponse {
  node_count: number;
  edge_count: number;
  graph_available: boolean;
  node_types: Record<string, number>;
}

export interface HealthResponse {
  status: string;
  version: string;
}
