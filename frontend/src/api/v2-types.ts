// frontend/src/api/v2-types.ts

export type KnowledgeType = "claim" | "question" | "setting" | "action";
export type ChainType = "deduction" | "induction" | "abstraction" | "contradiction" | "retraction";
export type PackageStatus = "preparing" | "submitted" | "merged" | "rejected";

export interface KnowledgeRef {
  knowledge_id: string;
  version: number;
}

export interface V2Knowledge {
  knowledge_id: string;
  version: number;
  type: KnowledgeType;
  content: string;
  prior: number;
  keywords: string[];
  source_package_id: string;
  source_package_version: string;
  source_module_id: string;
  created_at: string | null;
}

export interface ChainStep {
  step_index: number;
  premises: KnowledgeRef[];
  reasoning: string;
  conclusion: KnowledgeRef;
}

export interface V2Chain {
  chain_id: string;
  module_id: string;
  package_id: string;
  package_version: string;
  type: ChainType;
  steps: ChainStep[];
}

export interface ImportRef {
  knowledge_id: string;
  version: number;
  strength: string;
}

export interface V2Module {
  module_id: string;
  package_id: string;
  package_version: string;
  name: string;
  role: string;
  imports: ImportRef[];
  chain_ids: string[];
  export_ids: string[];
}

export interface V2Package {
  package_id: string;
  name: string;
  version: string;
  description: string;
  modules: string[];
  exports: string[];
  submitter: string;
  submitted_at: string;
  status: PackageStatus;
}

export interface V2ProbabilityRecord {
  chain_id: string;
  step_index: number;
  value: number;
  source: string;
  source_detail: string | null;
  recorded_at: string;
}

export interface V2BeliefSnapshot {
  knowledge_id: string;
  version: number;
  belief: number;
  bp_run_id: string;
  computed_at: string;
}

export interface V2Paginated<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface GraphNode {
  id: string;
  knowledge_id: string;
  version: number;
  type: KnowledgeType;
  content: string;
  prior: number;
}

export interface GraphEdge {
  chain_id: string;
  from: string;
  to: string;
  chain_type: ChainType;
  step_index: number;
}

/** @deprecated Use UnifiedGraphData instead */
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── Unified factor graph types (new /graph API) ──

export interface GraphKnowledgeNode {
  knowledge_id: string;
  version: number;
  type: string;
  kind: string | null;
  content: string;
  prior: number;
  belief: number | null;
  source_package_id: string;
  source_module_id: string;
}

export interface GraphFactorNode {
  factor_id: string;
  type: string;
  premises: string[];
  contexts: string[];
  conclusion: string;
  package_id: string;
  metadata: Record<string, unknown> | null;
}

export interface UnifiedGraphData {
  knowledge_nodes: GraphKnowledgeNode[];
  factor_nodes: GraphFactorNode[];
}
