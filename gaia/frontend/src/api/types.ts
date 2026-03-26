/** API response types for the Gaia LKM backend. */

export interface TableListResponse {
  tables: string[];
}

export interface TableDataResponse {
  table: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
}

export interface Neo4jStats {
  knowledge_node_count: number;
  factor_node_count: number;
  edge_count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string; // claim, setting, question, template, factor
  reasoning_type?: string; // for factors: deduction, induction, etc.
  belief?: number;
  prior?: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  role: string; // premise, conclusion
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  packages?: string[];
}

export interface HealthResponse {
  status: string;
}
