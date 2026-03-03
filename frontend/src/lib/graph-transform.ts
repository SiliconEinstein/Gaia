/**
 * Transform API Node[] + HyperEdge[] into vis-network DataSets.
 *
 * Uses a bipartite "factor graph" representation:
 * - Proposition nodes → ellipses/circles/diamonds
 * - HyperEdge → square factor node (F_{edge_id})
 * - tail nodes → factor (directed edge)
 * - factor → head nodes (directed edge)
 */
import type { Node as GaiaNode, HyperEdge } from "../api/types";
import { getNodeStyle, getFactorStyle } from "./node-styles";

export interface VisNode {
  id: string;
  label: string;
  title?: string;
  shape: string;
  color: { background: string; border: string };
  font?: { color?: string; size?: number; multi?: string };
  borderWidth?: number;
  size?: number;
  // Custom data for popups
  gaiaNode?: GaiaNode;
  gaiaEdge?: HyperEdge;
  isFactorNode?: boolean;
}

export interface VisEdge {
  id: string;
  from: string;
  to: string;
  arrows?: string;
  color?: { color: string; opacity?: number };
  dashes?: boolean;
  width?: number;
}

function truncate(s: string, max = 40): string {
  return s.length > max ? s.slice(0, max) + "..." : s;
}

function nodeLabel(n: GaiaNode): string {
  if (n.title) return truncate(n.title);
  const content =
    typeof n.content === "string" ? n.content : JSON.stringify(n.content);
  return truncate(content, 30);
}

function nodeTooltip(n: GaiaNode): string {
  const lines = [
    `ID: ${n.id}`,
    `Type: ${n.type}`,
    `Prior: ${n.prior}`,
  ];
  if (n.belief !== null) lines.push(`Belief: ${n.belief}`);
  if (n.keywords.length > 0) lines.push(`Keywords: ${n.keywords.join(", ")}`);
  return lines.join("\n");
}

export function transformSubgraph(
  nodes: GaiaNode[],
  edges: HyperEdge[]
): { visNodes: VisNode[]; visEdges: VisEdge[] } {
  const visNodes: VisNode[] = [];
  const visEdges: VisEdge[] = [];

  // 1. Add proposition nodes
  for (const n of nodes) {
    const style = getNodeStyle(n.type);
    visNodes.push({
      id: `n_${n.id}`,
      label: `${n.id}: ${nodeLabel(n)}`,
      title: nodeTooltip(n),
      shape: style.shape,
      color: style.color,
      font: { ...style.font, size: 12, multi: "html" },
      borderWidth: 2,
      size: 20,
      gaiaNode: n,
    });
  }

  // 2. Add factor nodes for each HyperEdge + connecting edges
  for (const e of edges) {
    const factorId = `f_${e.id}`;
    const fStyle = getFactorStyle(e.type);

    // Contradiction edges: direct red dashed line between nodes, no factor node
    if (e.type === "contradiction" && e.tail.length > 0 && e.head.length > 0) {
      for (const t of e.tail) {
        for (const h of e.head) {
          visEdges.push({
            id: `ce_${e.id}_${t}_${h}`,
            from: `n_${t}`,
            to: `n_${h}`,
            color: { color: "#EF4444" },
            dashes: true,
            width: 2,
            arrows: "",
          });
        }
      }
      // Also add a small factor node for clicking
      visNodes.push({
        id: factorId,
        label: `C${e.id}`,
        shape: "square",
        color: fStyle.color,
        font: { size: 9 },
        size: 10,
        borderWidth: 1,
        gaiaEdge: e,
        isFactorNode: true,
      });
      continue;
    }

    // Normal factor node
    const probLabel = e.probability !== null ? ` (${e.probability.toFixed(2)})` : "";
    visNodes.push({
      id: factorId,
      label: `E${e.id}${probLabel}`,
      title: `Edge ${e.id}\nType: ${e.type}\nVerified: ${e.verified}`,
      shape: "square",
      color: fStyle.color,
      font: { size: 10 },
      borderWidth: fStyle.dash ? 2 : 1,
      size: 14,
      gaiaEdge: e,
      isFactorNode: true,
    });

    // tail → factor
    for (const t of e.tail) {
      visEdges.push({
        id: `te_${e.id}_${t}`,
        from: `n_${t}`,
        to: factorId,
        arrows: "to",
        color: { color: fStyle.color.border, opacity: 0.6 },
        width: 1.5,
      });
    }

    // factor → head
    for (const h of e.head) {
      visEdges.push({
        id: `he_${e.id}_${h}`,
        from: factorId,
        to: `n_${h}`,
        arrows: "to",
        color: { color: fStyle.color.border, opacity: 0.6 },
        width: 1.5,
      });
    }
  }

  return { visNodes, visEdges };
}
