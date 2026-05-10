// Shared types for the starmap-replay v4 frontend.
//
// v4 changes:
//   • Time axis is per-`gaia_action` (one IR-tick per IR-relevant action),
//     not per-event. The CLI ships `ticks[]` precomputed.
//   • Layout is pinned: `final_layout` carries Graphviz-derived positions
//     for every node and bounding boxes for every cluster. d3-force is gone.
//   • Per-round belief snapshots: `round_beliefs[round_id]` is a
//     `{knowledge_id: belief}` table the canvas animates between.
//   • LKM-driven IR-ticks carry `retrieval_event_ids`, which the canvas
//     uses to flash a transient overlay near the affected node(s).
//
// Loose / pass-through-friendly: only fields the frontend actually consumes
// are typed; everything else flows through as `unknown` keys on the event.

export interface GraphNodeAdded {
  id: string;
  kind?: string;
  label?: string;
  lkm_id?: string;
  source_paper?: string;
  prior?: number;
  content_excerpt?: string;
}

export interface GraphNodeRemoved {
  id: string;
  kind?: string;
  reason?: string;
}

export interface GraphEdgeRecord {
  from: string;
  to: string;
  kind?: string;
  prior?: number;
  reason_excerpt?: string;
}

export interface GraphDelta {
  nodes_added: GraphNodeAdded[];
  edges_added: GraphEdgeRecord[];
  nodes_removed: GraphNodeRemoved[];
  edges_removed: GraphEdgeRecord[];
}

export interface FrontierClaim {
  label?: string;
  lkm_id?: string;
}

// gaia_actions[] entries — the canonical topology authority.
// `action` is one of: claim | deduction | support | contradiction |
// equivalence | prior | inquiry_hypothesis | inquiry_obligation | merge.
export interface GaiaAction {
  action: string;
  symbol?: string;
  file?: string;
  [k: string]: unknown;
}

export interface TimelineEvent {
  event_id: string;
  event_kind: 'retrieval' | 'growth';
  timestamp_utc: string;
  stage?: string;
  round_id?: string;
  actor?: string;
  actor_id?: string;
  seq?: number;
  channel?: string;
  decision?: string;
  frontier_claim?: FrontierClaim | null;
  payload?: Record<string, unknown>;
  graph_delta?: GraphDelta;
  gaia_actions?: GaiaAction[];
  scope_tuple?: Record<string, unknown> | null;
  scope_diff?: Record<string, unknown> | null;
  open_problem?: string | null;
  rejection_reason?: string | null;
  warrant_prior?: number | null;
  request?: Record<string, unknown>;
  result_summary?: Record<string, unknown>;
  retrieval_event_ids?: string[];
  notes?: string;
  [k: string]: unknown;
}

// IR-tick — one per IR-relevant gaia_action, baked by the CLI side.
export interface IrTick {
  tick_index: number;
  event_index: number;
  event_id: string;
  action_index: number;
  action: GaiaAction;
  round_id?: string | null;
  lkm_driven: boolean;
  retrieval_event_ids: string[];
  // True iff this tick's action references an entity present in the
  // final compiled IR. Orphan ticks (`false`) represent symbols the
  // agent admitted mid-run but later merged/repaired away — the timeline
  // marker still renders (desaturated) but the canonical canvas stays
  // unchanged so the replay's final state matches the static SVG.
  // Defaults to true when missing (backwards-compat with older payloads).
  survives_to_final?: boolean;
}

export interface LayoutNode {
  x: number;
  y: number;
  // Optional CLI-side annotation set by `annotate_layout_with_kinds`.
  // `kind` is one of: `knowledge` | `strategy` | `operator`. When absent,
  // the frontend falls back to id-prefix heuristics (legacy v3 behaviour).
  kind?: string;
  // Knowledge-class refinement: `setting` | `exported` | `derived` | `claim`.
  sub_kind?: string;
  // Strategy/operator subtypes (e.g. `deduction`, `support`, `contradiction`).
  strategy_type?: string;
  operator_type?: string;
  label?: string;
  exported?: boolean;
  prior?: number;
  module?: string | null;
  // For strategy/operator entries: conclusion + premise/variable layout
  // keys (post-rekey). The store co-admits these when the operator/
  // strategy lands so the final canvas mirrors `_dot.py`'s rendering
  // (which always emits the operator's conclusion claim as a knowledge
  // box even when no explicit `claim` event references it).
  conclusion_id?: string;
  premise_ids?: string[];
  variable_ids?: string[];
  // Canonical layout id (`strat_<i>` / `oper_<i>`) for entries the bridge
  // aliases to event-side symbol ids. The original strat_/oper_ entry
  // also carries its own id here. The store uses this to dedupe at
  // final-state reconciliation: one ellipse per strategy regardless of
  // how many event-symbol aliases share its position.
  canonical_id?: string;
}

export interface LayoutCluster {
  name: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  label_x: number;
  label_y: number;
}

export interface FinalLayout {
  viewport: { width: number; height: number };
  nodes: Record<string, LayoutNode>;
  clusters: LayoutCluster[];
}

export interface TimelinePayload {
  schema_version: string;
  package_name?: string | null;
  retrieval_count: number;
  growth_count: number;
  events: TimelineEvent[];
  ticks: IrTick[];
  rounds: string[];
  round_beliefs: Record<string, Record<string, number>>;
  final_layout: FinalLayout | null;
  build_warnings?: string[];
}

// Authoritative canonical state — built from `final_layout` and updated as
// IR-ticks land.
export interface CanonicalNode {
  id: string;
  // Pinned coordinates from the graphviz layout (already y-flipped to SVG
  // convention by the CLI). Always present once the node is admitted.
  x: number;
  y: number;
  // Class (claim / deduction / equivalence / strategy / operator / setting).
  kind: string;
  label: string;
  // Module (cluster) the node belongs to. `null` when the node floats
  // outside any cluster (cross_paper-style nodes).
  module: string | null;
  prior?: number;
  beliefByRound: Record<string, number>;
  contentExcerpt?: string;
  priorReason?: string;
  // True iff this node has been admitted by some IR-tick yet.
  admitted: boolean;
  // Tick index at which the node first became admitted (used for entrance
  // halo + LKM overlay sequencing). -1 when not yet admitted.
  admittedTick: number;
  removed: boolean;
}

export interface CanonicalEdge {
  key: string;
  from: string;
  to: string;
  kind: string;
  prior?: number;
  reason_excerpt?: string;
  operatorLabel?: string;
  operatorExcerpt?: string;
  admitted: boolean;
  admittedTick: number;
  removed: boolean;
}

// Color palette — single source of truth, used by all modules.
export const PALETTE = {
  bg: '#0e1116',
  bgElev: '#161b22',
  bgPanel: '#1b222b',
  fg: '#e6edf3',
  fgMute: '#8b949e',
  grid: '#2a3138',
  accent: '#58a6ff',

  // Semantic colours, shared across canvas + lanes + chips:
  accepted: '#22c55e',
  contradiction: '#ef4444',
  dismissed: '#eab308',
  hypothesis: '#94a3b8',
  retrieval: '#3b82f6',
  merge: '#a855f7',
  neutral: '#6b7280',
} as const;

// Retrieval-channel colour map.
export const RETRIEVAL_COLOURS: Record<string, string> = {
  root_discovery: '#60a5fa',
  support: '#22c55e',
  evidence_hydration: '#10b981',
  open_question_conflict: '#f97316',
  variables_hydration: '#a855f7',
  duplicate_review: '#eab308',
};

// Bucket the contract's growth-decision enum into colour families.
export const GROWTH_FAMILY: Record<string, string> = {
  package_initialized: PALETTE.neutral,
  stage_transition: PALETTE.neutral,
  round_open: PALETTE.neutral,
  round_close: PALETTE.neutral,
  user_selection_checkpoint_opened: PALETTE.neutral,
  user_selection_checkpoint_closed: PALETTE.neutral,
  selected_root: PALETTE.accent,

  accepted_support: PALETTE.accepted,
  accepted_claim: PALETTE.accepted,
  accepted_deduction: PALETTE.accepted,
  accepted_contradiction: PALETTE.contradiction,

  dismissed: PALETTE.dismissed,
  support_not_found: PALETTE.dismissed,
  conflict_not_found: PALETTE.dismissed,
  not_found: PALETTE.dismissed,
  needs_more_evidence: PALETTE.dismissed,

  equivalence: PALETTE.merge,
  merge: PALETTE.merge,
  keep_distinct: PALETTE.merge,

  repair: '#7c3aed',
  quality_gate_result: '#06b6d4',
  prior_added: '#06b6d4',

  hypothesis_added: PALETTE.hypothesis,
  obligation_added: PALETTE.hypothesis,
  hypothesis_only: PALETTE.hypothesis,

  candidate_considered: '#475569',
};

// Node fill / stroke per kind. Mirrors `_dot.py` `_knowledge_attrs`.
export const NODE_STYLE: Record<string, { fill: string; stroke: string }> = {
  claim: { fill: '#ddeeff', stroke: '#4488bb' },
  derived: { fill: '#ddffdd', stroke: '#44bb44' },
  exported: { fill: '#d4edda', stroke: '#28a745' },
  setting: { fill: '#f0f0f0', stroke: '#999999' },
  deduction: { fill: '#fff9c4', stroke: '#f9a825' },
  strategy: { fill: '#fff9c4', stroke: '#f9a825' },
  operator: { fill: '#fff9c4', stroke: '#f9a825' },
  contradiction: { fill: '#ffebee', stroke: '#c62828' },
  equivalence: { fill: '#fff9c4', stroke: '#f9a825' },
};

export const EDGE_COLOUR: Record<string, string> = {
  support: PALETTE.accepted,
  contradiction: PALETTE.contradiction,
  equivalence: PALETTE.merge,
  deduction: '#a855f7',
  inquiry: PALETTE.hypothesis,
  premise: '#666666',
  background: '#999999',
  conclusion: '#444444',
  variable: '#777777',
};

declare global {
  interface Window {
    TIMELINE_DATA?: TimelinePayload;
  }
}
