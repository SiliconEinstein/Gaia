import { useState, useCallback } from "react";
import { Alert, Spin } from "antd";
import { useSubgraph } from "../../hooks/useSubgraph";
import { transformSubgraph } from "../../lib/graph-transform";
import { GraphCanvas } from "./GraphCanvas";
import { GraphControls } from "./GraphControls";
import { GraphSearch } from "./GraphSearch";
import { GraphLegend } from "./GraphLegend";
import { NodePopup } from "./NodePopup";
import type { Node, HyperEdge } from "../../api/types";
import type { VisNode } from "../../lib/graph-transform";

interface Props {
  initialNodeId?: number;
  initialHops?: number;
}

export function SubgraphLoader({ initialNodeId, initialHops = 1 }: Props) {
  const [nodeId, setNodeId] = useState<number | null>(initialNodeId ?? null);
  const [hops, setHops] = useState(initialHops);
  const [physicsEnabled, setPhysicsEnabled] = useState(true);
  const [loadId, setLoadId] = useState<number | null>(initialNodeId ?? null);
  const [loadHops, setLoadHops] = useState(initialHops);

  // Popup state
  const [popupNode, setPopupNode] = useState<Node | undefined>();
  const [popupEdge, setPopupEdge] = useState<HyperEdge | undefined>();
  const [popupOpen, setPopupOpen] = useState(false);

  const { data, isLoading, error, refetch } = useSubgraph(loadId, loadHops);

  const handleLoad = useCallback(() => {
    if (nodeId !== null) {
      setLoadId(nodeId);
      setLoadHops(hops);
    }
  }, [nodeId, hops]);

  const handleSearchSelect = useCallback((id: number) => {
    setNodeId(id);
    setLoadId(id);
    setLoadHops(hops);
  }, [hops]);

  const handleNodeClick = useCallback(
    (visId: string) => {
      if (!data) return;

      // Find the clicked vis-node in data
      const allVisNodes = transformSubgraph(data.nodes, data.edges).visNodes;
      const clicked = allVisNodes.find((n: VisNode) => n.id === visId);
      if (!clicked) return;

      if (clicked.gaiaNode) {
        setPopupNode(clicked.gaiaNode);
        setPopupEdge(undefined);
      } else if (clicked.gaiaEdge) {
        setPopupEdge(clicked.gaiaEdge);
        setPopupNode(undefined);
      }
      setPopupOpen(true);
    },
    [data]
  );

  const graph = data ? transformSubgraph(data.nodes, data.edges) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
        <GraphControls
          nodeId={nodeId}
          hops={hops}
          physicsEnabled={physicsEnabled}
          onNodeIdChange={setNodeId}
          onHopsChange={setHops}
          onPhysicsToggle={setPhysicsEnabled}
          onReload={handleLoad}
          loading={isLoading}
        />
        <GraphSearch onSelectNode={handleSearchSelect} />
      </div>

      <GraphLegend />

      {error && (
        <Alert
          type="error"
          message="Failed to load subgraph"
          description={String(error)}
          style={{ marginBottom: 16 }}
        />
      )}

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" />
        </div>
      )}

      {graph && !isLoading && (
        <>
          <div style={{ color: "#888", fontSize: 12, marginBottom: 8 }}>
            {data!.nodes.length} nodes, {data!.edges.length} edges
          </div>
          <div style={{ flex: 1, minHeight: 500 }}>
            <GraphCanvas
              nodes={graph.visNodes}
              edges={graph.visEdges}
              onNodeClick={handleNodeClick}
              physicsEnabled={physicsEnabled}
            />
          </div>
        </>
      )}

      {!graph && !isLoading && !error && (
        <div
          style={{
            textAlign: "center",
            padding: 48,
            color: "#999",
            border: "1px dashed #d9d9d9",
            borderRadius: 8,
          }}
        >
          Enter a Node ID and click Load to visualize its subgraph
        </div>
      )}

      <NodePopup
        node={popupNode}
        edge={popupEdge}
        open={popupOpen}
        onClose={() => setPopupOpen(false)}
      />
    </div>
  );
}
