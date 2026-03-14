// frontend/src/lib/v2-graph-transform.ts
import type { GraphData, GraphNode, GraphEdge, KnowledgeType } from "../api/v2-types";

const TYPE_COLORS: Record<KnowledgeType, string> = {
  claim: "#1677ff",
  setting: "#52c41a",
  question: "#fa8c16",
  action: "#722ed1",
};

export interface VisNode {
  id: string;
  label: string;
  title: string;
  color: { background: string; border: string };
  font: { color: string };
  shape: "box";
}

export interface VisEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  arrows: "to";
  color: { color: string };
  font: { size: number };
}

export function toVisGraph(data: GraphData): { nodes: VisNode[]; edges: VisEdge[] } {
  const typeCounters: Partial<Record<KnowledgeType, number>> = {};
  const nodes: VisNode[] = data.nodes.map((n: GraphNode) => {
    typeCounters[n.type] = (typeCounters[n.type] ?? 0) + 1;
    const label = `${n.type} #${typeCounters[n.type]}`;
    return {
    id: n.id,
    label,
    title: `[${n.type}] ${n.content}\nprior: ${n.prior.toFixed(2)}`,
    color: {
      background: TYPE_COLORS[n.type] ?? "#aaa",
      border: "#333",
    },
    font: { color: "#fff" },
    shape: "box",
    };
  });

  const edgeMap = new Map<string, VisEdge>();
  data.edges.forEach((e: GraphEdge) => {
    const key = `${e.from}->${e.to}`;
    if (!edgeMap.has(key)) {
      edgeMap.set(key, {
        id: `${e.chain_id}:${e.step_index}:${e.from}:${e.to}`,
        from: e.from,
        to: e.to,
        label: e.chain_type,
        arrows: "to",
        color: { color: "#888" },
        font: { size: 10 },
      });
    }
  });

  return { nodes, edges: Array.from(edgeMap.values()) };
}

export const HIERARCHICAL_OPTIONS = {
  layout: { improvedLayout: true },
  physics: {
    enabled: true,
    barnesHut: {
      gravitationalConstant: -8000,
      centralGravity: 0.3,
      springLength: 160,
      springConstant: 0.04,
      damping: 0.09,
    },
    stabilization: { iterations: 200 },
  },
  interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true },
  nodes: { borderWidth: 1, borderWidthSelected: 2 },
  edges: { smooth: { type: "dynamic" }, arrows: { to: { scaleFactor: 0.6 } } },
};
