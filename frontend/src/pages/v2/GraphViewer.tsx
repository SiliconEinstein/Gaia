// frontend/src/pages/v2/GraphViewer.tsx
import { useEffect, useRef, useState } from "react";
import { Card, Select, Typography, Spin, Drawer } from "antd";
import { Network, DataSet } from "vis-network/standalone";
import { Link } from "react-router-dom";
import { useGraphData, usePackages, useKnowledge } from "../../api/v2";
import { toVisGraph, HIERARCHICAL_OPTIONS } from "../../lib/v2-graph-transform";

export function GraphViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [packageId, setPackageId] = useState<string | undefined>();
  const [selectedKnowledgeId, setSelectedKnowledgeId] = useState<string | null>(null);

  const { data: packages } = usePackages(1, 100);
  const { data: graphData, isLoading } = useGraphData(packageId);

  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    const { nodes, edges } = toVisGraph(graphData);
    const nodeDs = new DataSet(nodes);
    const edgeDs = new DataSet(edges);

    const net = new Network(
      containerRef.current,
      { nodes: nodeDs, edges: edgeDs },
      HIERARCHICAL_OPTIONS,
    );

    net.on("click", (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0] as string;
        // nodeId format: knowledge_id@version — strip the @version suffix
        const parts = nodeId.split("@");
        const knowledgeId = parts.slice(0, -1).join("@");
        setSelectedKnowledgeId(knowledgeId);
      }
    });

    networkRef.current = net;

    return () => {
      net.destroy();
      networkRef.current = null;
    };
  }, [graphData]);

  const packageOptions = (packages?.items ?? []).map((p) => ({
    value: p.package_id,
    label: p.package_id,
  }));

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>Graph IR</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Filter by package (all if empty)"
          style={{ width: 400 }}
          options={packageOptions}
          onChange={(v) => setPackageId(v)}
        />
        <Typography.Text style={{ marginLeft: 16, color: "#888" }}>
          {graphData ? `${graphData.nodes.length} nodes · ${graphData.edges.length} edges` : ""}
        </Typography.Text>
      </Card>
      <div style={{ position: "relative", width: "100%", height: "70vh" }}>
        <div
          ref={containerRef}
          style={{
            width: "100%",
            height: "100%",
            border: "1px solid #e8e8e8",
            borderRadius: 6,
            background: "#fafafa",
          }}
        />
        {isLoading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Spin size="large" />
          </div>
        )}
      </div>
      <Drawer
        title={
          selectedKnowledgeId ? (
            <Link to={`/v2/knowledge/${encodeURIComponent(selectedKnowledgeId)}`}>
              {selectedKnowledgeId}
            </Link>
          ) : "Knowledge"
        }
        open={!!selectedKnowledgeId}
        onClose={() => setSelectedKnowledgeId(null)}
        width={520}
      >
        {selectedKnowledgeId && <KnowledgeDetailInline id={selectedKnowledgeId} />}
      </Drawer>
    </div>
  );
}

function KnowledgeDetailInline({ id }: { id: string }) {
  const { data: k, isLoading } = useKnowledge(id);
  if (isLoading) return <Spin />;
  if (!k) return <Typography.Text type="danger">Not found</Typography.Text>;
  return (
    <div>
      <Typography.Text type="secondary">{k.type}</Typography.Text>
      <Typography.Paragraph style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
        {k.content}
      </Typography.Paragraph>
      <Typography.Text>Prior: {k.prior.toFixed(2)}</Typography.Text>
    </div>
  );
}
