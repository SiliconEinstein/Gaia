import Graph from 'graphology';
import Sigma from 'sigma';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import type { GraphData, AnyNode, EdgeRole, GraphEdge } from './types';
import { isStrategy, isOperator, isGeneratedHelper } from './types';

// --------------------------------------------------------------------------
// Color helpers
// --------------------------------------------------------------------------

function hex(r: number, g: number, b: number): string {
  const c = (n: number) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`;
}

/** belief color: red(0) -> grey(0.5) -> green(1). */
export function beliefColor(belief: number): string {
  const b = Math.max(0, Math.min(1, belief));
  if (b < 0.5) {
    // red -> grey
    const t = b * 2; // 0..1
    return hex(231 + (136 - 231) * t, 76 + (136 - 76) * t, 60 + (136 - 60) * t);
  }
  // grey -> green
  const t = (b - 0.5) * 2;
  return hex(136 + (46 - 136) * t, 136 + (204 - 136) * t, 136 + (113 - 136) * t);
}

/**
 * Support/lowering color for a signed strategy effect in [-1, 1]: red =
 * lowers the conclusion, grey = neutral, green = supports it. Reuses
 * `beliefColor`'s red-grey-green ramp via `t = (effect + 1) / 2` so nodes
 * (belief) and edges (effect) read as the same visual language. Mirrored in
 * `gaia/cli/commands/_dot.py::_effect_color` for the static SVG — keep the
 * two in sync.
 */
export function effectColor(effect: number): string {
  return beliefColor((effect + 1) / 2);
}

const NEUTRAL = '#888888';
const STRATEGY_COLOR = '#5b8def';
const OPERATOR_COLOR = '#a266ff';
/** Shrunk, dimmed size for generated/helper knowledge nodes (see isGeneratedHelper). */
const GENERATED_HELPER_SIZE = 3;

const EDGE_COLORS: Record<EdgeRole, string> = {
  premise: '#3a4a6c',
  background: '#2a334a',
  conclusion: '#6e8cc7',
  variable: '#4a3a6c',
};

const EDGE_SIZE: Record<EdgeRole, number> = {
  premise: 1.0,
  background: 0.6,
  conclusion: 2.0,
  variable: 1.0,
};

/**
 * Color + size for one edge. Conclusion edges with a computed `effect`
 * (infer/noisy_and strategies — see `_graph_json._strategy_effect`) are
 * colored by sign and thickened by magnitude instead of the flat role
 * color, so support/lowering is legible without opening the side panel.
 * Edges without an effect (unscored strategy forms, or non-conclusion
 * roles) keep the plain role styling.
 */
function edgeStyle(e: GraphEdge): { color: string; size: number } {
  if (e.role === 'conclusion' && typeof e.effect === 'number') {
    return {
      color: effectColor(e.effect),
      size: EDGE_SIZE.conclusion * (1 + Math.abs(e.effect) * 1.1),
    };
  }
  return { color: EDGE_COLORS[e.role] || '#3a4a6c', size: EDGE_SIZE[e.role] || 1 };
}

// --------------------------------------------------------------------------
// Build graphology Graph from GraphData
// --------------------------------------------------------------------------

export interface NodeViz {
  id: string;
  raw: AnyNode;
  type: string; // gaia node type
  label: string;
  size: number;
  color: string;
  shape: 'circle' | 'square'; // for our own use; sigma renders as circles by default
  belief: number | null;
  hasBeliefDashed: boolean;
}

function nodeLabel(n: AnyNode): string {
  if (isStrategy(n)) return `▸ ${n.strategy_type || 'strategy'}`;
  if (isOperator(n)) return `◆ ${n.operator_type || 'operator'}`;
  return n.label || n.id;
}

function nodeSize(n: AnyNode): number {
  if (isStrategy(n) || isOperator(n)) return 4;
  if (isGeneratedHelper(n)) return GENERATED_HELPER_SIZE;
  // boost size by belief; default 6, peaks at 12 if belief high
  const k = n as { belief?: number | null };
  const b = k.belief == null ? 0.5 : k.belief;
  return 5 + b * 5;
}

function nodeColor(n: AnyNode): string {
  if (isStrategy(n)) return STRATEGY_COLOR;
  if (isOperator(n)) return OPERATOR_COLOR;
  const k = n as { belief?: number | null };
  if (k.belief == null) return NEUTRAL;
  return beliefColor(k.belief);
}

function nodeKind(n: AnyNode): string {
  if (isStrategy(n)) return 'strategy';
  if (isOperator(n)) return 'operator';
  if (isGeneratedHelper(n)) return 'generated';
  return n.type || 'unknown';
}

export function buildGraph(data: GraphData): Graph {
  const g = new Graph({ multi: false, type: 'directed' });

  // Generated/helper knowledge nodes (compiler-minted provenance, e.g. the
  // "likelihood" claim infer() auto-writes) start collapsed so they don't
  // dominate the layout; the filter panel's "generated" toggle reveals them
  // on demand. Track their ids so incident edges start collapsed too —
  // otherwise sigma would draw edges dangling off an invisible endpoint.
  const generatedIds = new Set(data.nodes.filter(isGeneratedHelper).map((n) => n.id));

  // seed positions on a circle so the worker has something non-degenerate
  const N = data.nodes.length || 1;
  data.nodes.forEach((n, i) => {
    if (g.hasNode(n.id)) return;
    const angle = (i / N) * Math.PI * 2;
    const r = 100 + Math.random() * 40;
    g.addNode(n.id, {
      x: Math.cos(angle) * r + (Math.random() - 0.5) * 20,
      y: Math.sin(angle) * r + (Math.random() - 0.5) * 20,
      label: nodeLabel(n),
      size: nodeSize(n),
      color: nodeColor(n),
      kind: nodeKind(n),
      raw: n,
      hidden: generatedIds.has(n.id),
      // dashed border if no belief and is a knowledge node
      borderColor: !isStrategy(n) && !isOperator(n) && (n as { belief?: number | null }).belief == null
        ? '#555' : undefined,
    });
  });

  let dropped = 0;
  data.edges.forEach((e, i) => {
    if (!g.hasNode(e.source) || !g.hasNode(e.target)) {
      dropped++;
      return;
    }
    const id = `e${i}`;
    if (g.hasEdge(id)) return;
    const style = edgeStyle(e);
    g.addEdgeWithKey(id, e.source, e.target, {
      role: e.role,
      effect: e.effect ?? null,
      color: style.color,
      size: style.size,
      type: e.role === 'background' ? 'arrow' : 'arrow',
      hidden: generatedIds.has(e.source) || generatedIds.has(e.target),
    });
  });
  if (dropped) console.warn(`[starmap] dropped ${dropped} edges with missing endpoints`);

  return g;
}

// --------------------------------------------------------------------------
// Layout (forceatlas2 worker)
// --------------------------------------------------------------------------

export interface LayoutHandle {
  start(): void;
  stop(): void;
  isRunning(): boolean;
}

export function runLayout(g: Graph, iterations = 600): LayoutHandle {
  const settings = forceAtlas2.inferSettings(g);
  const layout = new FA2Layout(g, {
    settings: {
      ...settings,
      slowDown: 5,
      gravity: 1,
      scalingRatio: 8,
      strongGravityMode: false,
      barnesHutOptimize: g.order > 1500,
    },
  });

  let running = false;
  let timer: number | undefined;

  return {
    start() {
      if (running) return;
      running = true;
      layout.start();
      // auto-stop after a fixed wall-clock window roughly proportional to iterations
      const ms = Math.min(15_000, Math.max(2500, iterations * 8));
      timer = window.setTimeout(() => {
        layout.stop();
        running = false;
      }, ms);
    },
    stop() {
      if (timer) window.clearTimeout(timer);
      layout.stop();
      running = false;
    },
    isRunning() {
      return running;
    },
  };
}

// --------------------------------------------------------------------------
// Sigma initialization
// --------------------------------------------------------------------------

export function initSigma(container: HTMLElement, graph: Graph): Sigma {
  const renderer = new Sigma(graph, container, {
    renderEdgeLabels: false,
    enableEdgeEvents: false,
    defaultEdgeType: 'arrow',
    labelColor: { color: '#cfd6e4' },
    labelSize: 12,
    labelWeight: '500',
    labelDensity: 0.7,
    labelGridCellSize: 80,
    labelRenderedSizeThreshold: 6, // hide labels for small nodes when zoomed out
    minCameraRatio: 0.05,
    maxCameraRatio: 8,
    zIndex: false,
    // keep WebGL programs default — circle nodes + arrow edges
  });

  return renderer;
}
