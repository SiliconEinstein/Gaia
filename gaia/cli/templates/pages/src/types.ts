// --- Node types ---

export interface KnowledgeNode {
  id: string
  label: string
  title?: string
  type: 'claim' | 'setting' | 'question' | 'action'
  module?: string
  content: string
  prior?: number | null
  belief?: number | null
  exported: boolean
  metadata: Record<string, unknown>
}

export interface StrategyNode {
  id: string
  type: 'strategy'
  strategy_type: string
  module?: string
  reason?: string
}

export interface OperatorNode {
  id: string
  type: 'operator'
  operator_type: string
  module?: string
}

export type GraphNode = KnowledgeNode | StrategyNode | OperatorNode

// --- Edge types ---

export interface GraphEdge {
  source: string
  target: string
  role: 'premise' | 'background' | 'conclusion' | 'variable'
}

// --- Module types ---

export interface ModuleInfo {
  id: string
  order: number
  node_count: number
  strategy_count: number
}

export interface CrossModuleEdge {
  from_module: string
  to_module: string
  count: number
}

// --- Top-level data ---

export interface GraphData {
  modules: ModuleInfo[]
  cross_module_edges: CrossModuleEdge[]
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface MetaData {
  package_name: string
  namespace: string
  description?: string
}

// --- Type guards ---

export function isKnowledgeNode(n: GraphNode): n is KnowledgeNode {
  return n.type === 'claim' || n.type === 'setting' || n.type === 'question' || n.type === 'action'
}

export function isStrategyNode(n: GraphNode): n is StrategyNode {
  return n.type === 'strategy'
}

export function isOperatorNode(n: GraphNode): n is OperatorNode {
  return n.type === 'operator'
}
