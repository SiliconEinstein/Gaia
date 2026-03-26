import { useEffect, useRef } from 'react';
import { Network, type Options } from 'vis-network';
import { DataSet } from 'vis-data';

interface GraphNode {
  id: string;
  label: string;
  type: string;
  reasoning_type?: string;
  belief?: number;
  prior?: number;
}

interface GraphEdge {
  from: string;
  to: string;
  role: string;
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  claim: '#1890ff',
  setting: '#52c41a',
  question: '#faad14',
  template: '#722ed1',
};

const FACTOR_COLOR = '#ff4d4f';

function nodeShape(type: string): string {
  if (type === 'factor') return 'box';
  return 'dot';
}

function nodeColor(node: GraphNode): string {
  if (node.type === 'factor') return FACTOR_COLOR;
  return NODE_COLORS[node.type] ?? '#999';
}

function buildLabel(node: GraphNode): string {
  let lbl = node.label || node.id;
  // Truncate long labels
  if (lbl.length > 40) lbl = lbl.slice(0, 37) + '...';
  if (node.belief != null) {
    lbl += `\nb=${node.belief.toFixed(3)}`;
  }
  return lbl;
}

export default function GraphCanvas({ nodes, edges }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Deduplicate nodes by id (same lcn_ can appear from multiple packages)
    const seen = new Set<string>();
    const uniqueNodes = nodes.filter((n) => {
      if (seen.has(n.id)) return false;
      seen.add(n.id);
      return true;
    });

    const visNodes = new DataSet(
      uniqueNodes.map((n) => ({
        id: n.id,
        label: buildLabel(n),
        shape: nodeShape(n.type),
        color: {
          background: nodeColor(n),
          border: nodeColor(n),
          highlight: { background: nodeColor(n), border: '#333' },
        },
        font: { color: '#fff', size: n.type === 'factor' ? 10 : 12 },
        size: n.type === 'factor' ? 12 : 20,
        title: `${n.id}\ntype: ${n.type}${n.reasoning_type ? `\nreasoning: ${n.reasoning_type}` : ''}${n.belief != null ? `\nbelief: ${n.belief}` : ''}${n.prior != null ? `\nprior: ${n.prior}` : ''}`,
      }))
    );

    const visEdges = new DataSet(
      edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        arrows: 'to',
        label: e.role,
        font: { size: 9, color: '#888' },
        color: { color: '#bbb' },
      }))
    );

    const options: Options = {
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -80,
          centralGravity: 0.01,
          springLength: 120,
          springConstant: 0.04,
        },
        stabilization: { iterations: 200 },
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
      },
      layout: {
        improvedLayout: true,
      },
    };

    networkRef.current = new Network(
      containerRef.current,
      { nodes: visNodes, edges: visEdges },
      options
    );

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, [nodes, edges]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => networkRef.current?.fit();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: 'calc(100vh - 200px)', border: '1px solid #f0f0f0', borderRadius: 8 }}
    />
  );
}
