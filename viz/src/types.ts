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
  /** Full CPT for infer/noisy_and strategies; null/absent for other forms. */
  conditional_probabilities?: number[] | null;
  /**
   * Signed support/lowering effect on the conclusion, in [-1, 1].
   * Positive = the premise raises belief in the conclusion (support),
   * negative = it lowers it. null when the strategy form (support/
   * deduction/...) carries no strategy-level CPT to derive this from.
   */
  effect?: number | null;
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
  /** Signed support/lowering effect, mirrored from the source strategy node. */
  effect?: number | null;
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

/**
 * True for knowledge nodes the compiler/reviewer minted as provenance —
 * e.g. the "likelihood" claim `infer(...)` auto-generates to spell out
 * p(e|h)/p(e|not h) in prose (see `gaia.engine.lang.dsl.infer_verb`) — as
 * opposed to content a person actually authored. Useful provenance, but not
 * meant to dominate the layout by default (see `docs/foundations/gaia-ir/
 * 04-helper-claims.md` for the broader "helper claim" contract).
 */
export function isGeneratedHelper(n: AnyNode): boolean {
  if (isStrategy(n) || isOperator(n)) return false;
  const metadata = (n as KnowledgeNode).metadata;
  return metadata?.generated === true;
}
