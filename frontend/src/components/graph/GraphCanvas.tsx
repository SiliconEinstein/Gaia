import { useRef, useEffect, useCallback } from "react";
import { Network, DataSet } from "vis-network/standalone";
import type { VisNode, VisEdge } from "../../lib/graph-transform";
import { PHYSICS_OPTIONS } from "../../lib/node-styles";

interface Props {
  nodes: VisNode[];
  edges: VisEdge[];
  onNodeClick?: (nodeId: string) => void;
  physicsEnabled?: boolean;
}

export function GraphCanvas({
  nodes,
  edges,
  onNodeClick,
  physicsEnabled = true,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  const handleClick = useCallback(
    (params: { nodes: string[] }) => {
      if (params.nodes.length > 0 && onNodeClick) {
        onNodeClick(params.nodes[0]);
      }
    },
    [onNodeClick]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const nodesDS = new DataSet(nodes as never[]);
    const edgesDS = new DataSet(edges as never[]);

    const network = new Network(
      containerRef.current,
      { nodes: nodesDS, edges: edgesDS },
      {
        physics: physicsEnabled ? PHYSICS_OPTIONS : false,
        interaction: {
          hover: true,
          tooltipDelay: 200,
          multiselect: true,
          navigationButtons: true,
        },
        edges: {
          smooth: { type: "continuous" },
        },
        layout: {
          improvedLayout: nodes.length < 200,
        },
      }
    );

    network.on("click", handleClick);

    // Stop physics after stabilization so the graph doesn't keep bouncing
    network.on("stabilized", () => {
      network.setOptions({ physics: false });
    });

    networkRef.current = network;

    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, [nodes, edges, physicsEnabled, handleClick]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: 500,
        border: "1px solid #d9d9d9",
        borderRadius: 8,
        background: "#fff",
      }}
    />
  );
}
