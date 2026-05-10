// Mirrors gaia/cli/commands/_graph_json.py output shape.

export type EdgeRole = 'premise' | 'background' | 'conclusion' | 'variable';

export interface ModuleEntry {
  id: string;
  order: number;
  node_count: number;
  strategy_count: number;
}

export interface CrossModuleEdge {
  from_module: string;
  to_module: string;
  count: number;
}

export interface KnowledgeNode {
  id: string;
  label?: string;
  title?: string;
  type: string; // claim | question | setting | background | ...
  module?: string;
  content?: string;
  prior?: number | null;
  belief?: number | null;
  exported?: boolean;
  metadata?: Record<string, unknown>;
}

export interface StrategyNode {
  id: string;
  type: 'strategy';
  strategy_type: string;
  module?: string;
  reason?: string;
}

export interface OperatorNode {
  id: string;
  type: 'operator';
  operator_type: string;
  module?: string;
}

export type AnyNode = KnowledgeNode | StrategyNode | OperatorNode;

export interface GraphEdge {
  source: string;
  target: string;
  role: EdgeRole;
}

export interface GraphData {
  modules: ModuleEntry[];
  cross_module_edges: CrossModuleEdge[];
  nodes: AnyNode[];
  edges: GraphEdge[];
}

export function isStrategy(n: AnyNode): n is StrategyNode {
  return (n as StrategyNode).type === 'strategy';
}

export function isOperator(n: AnyNode): n is OperatorNode {
  return (n as OperatorNode).type === 'operator';
}
