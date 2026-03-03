/** Node and edge visual styles for vis-network, ported from the Python visualization code. */

export interface NodeStyle {
  shape: string;
  color: { background: string; border: string };
  font?: { color: string };
}

export interface FactorStyle {
  color: { background: string; border: string };
  dash?: boolean;
}

/** Proposition node styles by type */
export const NODE_STYLES: Record<string, NodeStyle> = {
  "paper-extract": {
    shape: "ellipse",
    color: { background: "#DBEAFE", border: "#3B82F6" },
  },
  premise: {
    shape: "ellipse",
    color: { background: "#DBEAFE", border: "#3B82F6" },
  },
  conclusion: {
    shape: "ellipse",
    color: { background: "#FECACA", border: "#EF4444" },
  },
  join: {
    shape: "dot",
    color: { background: "#FED7AA", border: "#FB923C" },
  },
  deduction: {
    shape: "ellipse",
    color: { background: "#CFFAFE", border: "#06B6D4" },
  },
  conjecture: {
    shape: "diamond",
    color: { background: "#E9D5FF", border: "#A855F7" },
  },
  divergence: {
    shape: "diamond",
    color: { background: "#F43F5E", border: "#9F1239" },
    font: { color: "#ffffff" },
  },
};

/** Hyperedge factor node styles by type */
export const FACTOR_STYLES: Record<string, FactorStyle> = {
  "paper-extract": {
    color: { background: "#D1FAE5", border: "#10B981" },
  },
  join: {
    color: { background: "#FED7AA", border: "#FB923C" },
  },
  meet: {
    color: { background: "#E9D5FF", border: "#A855F7" },
  },
  contradiction: {
    color: { background: "#FEE2E2", border: "#EF4444" },
    dash: true,
  },
  retraction: {
    color: { background: "#FEF3C7", border: "#F59E0B" },
  },
};

const DEFAULT_NODE_STYLE: NodeStyle = {
  shape: "ellipse",
  color: { background: "#F3F4F6", border: "#9CA3AF" },
};

const DEFAULT_FACTOR_STYLE: FactorStyle = {
  color: { background: "#E5E7EB", border: "#6B7280" },
};

export function getNodeStyle(type: string): NodeStyle {
  return NODE_STYLES[type] ?? DEFAULT_NODE_STYLE;
}

export function getFactorStyle(type: string): FactorStyle {
  return FACTOR_STYLES[type] ?? DEFAULT_FACTOR_STYLE;
}

/** Physics simulation config (from visualize_inference_paths.py) */
export const PHYSICS_OPTIONS = {
  solver: "barnesHut" as const,
  barnesHut: {
    gravitationalConstant: -8000,
    centralGravity: 0.3,
    springLength: 150,
    springConstant: 0.04,
    damping: 0.09,
    avoidOverlap: 0.5,
  },
  stabilization: {
    iterations: 200,
    updateInterval: 25,
  },
};
