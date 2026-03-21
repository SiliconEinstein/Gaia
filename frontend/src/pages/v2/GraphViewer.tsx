// frontend/src/pages/v2/GraphViewer.tsx
import { useEffect, useRef, useState } from "react";
import { Card, Select, Typography, Spin, Drawer, Tag } from "antd";
import { Network, DataSet } from "vis-network/standalone";
import { usePackages, useUnifiedGraph } from "../../api/v2";
import type { UnifiedGraphData } from "../../api/v2-types";
import { Link } from "react-router-dom";

// ── Colors ──

const TYPE_COLORS: Record<string, string> = {
  claim: "#1677ff",
  schema: "#9254de",  // abstraction nodes from curation
  setting: "#52c41a",
  question: "#fa8c16",
  action: "#722ed1",
  contradiction: "#f5222d",
  equivalence: "#13c2c2",
};

const FACTOR_COLORS: Record<string, string> = {
  infer: "#595959",
  abstraction: "#595959",
  instantiation: "#8c8c8c",
  contradiction: "#cf1322",
  equivalence: "#08979c",
};

// ── Vis transform ──

function truncateName(knowledgeId: string, maxLen = 25): string {
  const parts = knowledgeId.split("/");
  const name = parts.length > 1 ? parts.slice(1).join("/") : knowledgeId;
  return name.length > maxLen ? name.slice(0, maxLen - 2) + "\u2026" : name;
}

function buildVisGraph(data: UnifiedGraphData) {
  const nodes: {
    id: string;
    label: string;
    title: string;
    color: { background: string; border: string };
    font: { color: string; size: number };
    shape: string;
    size: number;
    borderWidth: number;
  }[] = [];
  const edges: {
    id: string;
    from: string;
    to: string;
    arrows: string;
    color: { color: string };
    dashes?: boolean;
    label?: string;
    font?: { size: number; color: string };
  }[] = [];

  for (const n of data.knowledge_nodes) {
    const shortName = truncateName(n.knowledge_id);
    const belief = n.belief != null ? n.belief : n.prior;
    const delta = belief - n.prior;
    const deltaStr = delta >= 0 ? `+${delta.toFixed(3)}` : delta.toFixed(3);
    const label = `${shortName}\n${belief.toFixed(2)}`;

    const tooltip = [
      `[${n.type}] ${n.knowledge_id}`,
      n.content.trim().slice(0, 300),
      `prior: ${n.prior.toFixed(3)}  →  belief: ${belief.toFixed(3)}  (${deltaStr})`,
      `package: ${n.source_package_id}`,
      `module: ${n.source_module_id}`,
    ].join("\n");

    // Schema (abstraction) nodes get distinct color and larger size
    const isSchema = n.kind === "schema";
    const bgColor = isSchema ? TYPE_COLORS.schema : (TYPE_COLORS[n.type] ?? "#aaa");

    nodes.push({
      id: n.knowledge_id,
      label: isSchema ? `⬡ ${label}` : label,
      title: tooltip,
      color: {
        background: bgColor,
        border: isSchema ? "#531dab" : "#555",
      },
      font: { color: "#fff", size: isSchema ? 12 : 10 },
      shape: "box",
      size: isSchema ? 20 : 14,
      borderWidth: isSchema ? 2 : 1,
    });
  }

  for (const f of data.factor_nodes) {
    const tooltip = [
      `[factor: ${f.type}] ${f.factor_id}`,
      `premises: ${f.premises.length}, contexts: ${f.contexts.length}`,
      `package: ${f.package_id}`,
    ].join("\n");

    nodes.push({
      id: f.factor_id,
      label: f.type,
      title: tooltip,
      color: {
        background: FACTOR_COLORS[f.type] ?? "#595959",
        border: FACTOR_COLORS[f.type] ?? "#595959",
      },
      font: { color: "#fff", size: 8 },
      shape: "box",
      size: 6,
      borderWidth: 0,
    });

    for (const p of f.premises) {
      edges.push({
        id: `${p}->${f.factor_id}`,
        from: p,
        to: f.factor_id,
        arrows: "",
        color: { color: "#595959" },
      });
    }
    for (const c of f.contexts) {
      edges.push({
        id: `${c}->${f.factor_id}:ctx`,
        from: c,
        to: f.factor_id,
        arrows: "",
        color: { color: "#d9d9d9" },
        dashes: true,
      });
    }
    if (f.conclusion) {
      edges.push({
        id: `${f.factor_id}->${f.conclusion}`,
        from: f.factor_id,
        to: f.conclusion,
        arrows: "to",
        color: {
          color:
            f.type === "contradiction" || f.type === "equivalence"
              ? (FACTOR_COLORS[f.type] ?? "#595959")
              : "#595959",
        },
      });
    }
  }

  return { nodes, edges };
}

// ── Layout options ──

const SHARED_OPTIONS = {
  interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true, dragNodes: true },
  nodes: { borderWidth: 1, borderWidthSelected: 3 },
  edges: {
    arrows: { to: { scaleFactor: 0.4 } },
    font: { size: 8, color: "#999" },
    color: { opacity: 0.7 },
  },
};

// Per-package: hierarchical top-down
const HIERARCHICAL_OPTIONS = {
  ...SHARED_OPTIONS,
  layout: {
    hierarchical: {
      enabled: true,
      direction: "UD",
      sortMethod: "directed",
      levelSeparation: 50,
      nodeSpacing: 160,
      treeSpacing: 80,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true,
    },
  },
  physics: { enabled: false },
  edges: {
    ...SHARED_OPTIONS.edges,
    smooth: { type: "cubicBezier", forceDirection: "vertical", roundness: 0.3 },
  },
};

// Global: force-directed gravity layout
const GRAVITY_OPTIONS = {
  ...SHARED_OPTIONS,
  layout: { hierarchical: { enabled: false } },
  physics: {
    enabled: true,
    barnesHut: {
      gravitationalConstant: -6000,
      centralGravity: 0.5,
      springLength: 120,
      springConstant: 0.02,
      damping: 0.3,
    },
    stabilization: { iterations: 200, fit: true },
  },
  edges: {
    ...SHARED_OPTIONS.edges,
    smooth: { type: "continuous" },
  },
};

// ── Graph canvas component ──

function FactorGraphCanvas({
  data,
  onSelectNode,
  height = "70vh",
  useGravity = false,
}: {
  data: UnifiedGraphData | undefined;
  onSelectNode: (id: string) => void;
  height?: string | number;
  useGravity?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const onSelectNodeRef = useRef(onSelectNode);
  onSelectNodeRef.current = onSelectNode;

  useEffect(() => {
    if (!containerRef.current || !data) return;
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    const { nodes, edges } = buildVisGraph(data);
    const net = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet(edges) },
      useGravity ? GRAVITY_OPTIONS : HIERARCHICAL_OPTIONS,
    );
    net.on("click", (p) => {
      if (p.nodes.length > 0) onSelectNodeRef.current(p.nodes[0] as string);
    });
    networkRef.current = net;
    return () => {
      net.destroy();
      networkRef.current = null;
    };
  }, [data, useGravity]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height,
        minHeight: 400,
        border: "1px solid #e8e8e8",
        borderRadius: 6,
        background: "#fafafa",
      }}
    />
  );
}

// ── Node detail drawer ──

function NodeDetailDrawer({
  nodeId,
  data,
  onClose,
}: {
  nodeId: string | null;
  data: UnifiedGraphData | undefined;
  onClose: () => void;
}) {
  if (!nodeId || !data) return null;

  const kNode = data.knowledge_nodes.find((n) => n.knowledge_id === nodeId);
  const fNode = data.factor_nodes.find((f) => f.factor_id === nodeId);

  const title = kNode ? (
    <Link to={`/v2/knowledge/${encodeURIComponent(kNode.knowledge_id)}`}>
      {kNode.knowledge_id}
    </Link>
  ) : fNode ? (
    fNode.factor_id
  ) : (
    "Node Detail"
  );

  return (
    <Drawer title={title} open={!!nodeId} onClose={onClose} width={560}>
      {kNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={TYPE_COLORS[kNode.type]}>{kNode.type}</Tag>
            {kNode.kind && <Tag>{kNode.kind}</Tag>}
          </div>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {kNode.knowledge_id} (v{kNode.version})
          </Typography.Text>
          <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
            {kNode.content}
          </Typography.Paragraph>
          <div style={{ marginTop: 8 }}>
            <Typography.Text strong>Prior: {kNode.prior.toFixed(3)}</Typography.Text>
          </div>
          <div style={{ marginTop: 8 }}>
            <Typography.Text type="secondary">
              Package: {kNode.source_package_id}
            </Typography.Text>
          </div>
          <div>
            <Typography.Text type="secondary">
              Module: {kNode.source_module_id}
            </Typography.Text>
          </div>
        </div>
      )}
      {fNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={FACTOR_COLORS[fNode.type] ?? "#595959"}>{fNode.type}</Tag>
          </div>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {fNode.factor_id}
          </Typography.Text>
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong>Premises ({fNode.premises.length}):</Typography.Text>
            {fNode.premises.map((p) => (
              <div key={p}>
                <Typography.Text code style={{ fontSize: 10 }}>
                  {p}
                </Typography.Text>
              </div>
            ))}
          </div>
          {fNode.contexts.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Typography.Text strong>Contexts ({fNode.contexts.length}):</Typography.Text>
              {fNode.contexts.map((c) => (
                <div key={c}>
                  <Typography.Text code style={{ fontSize: 10 }}>
                    {c}
                  </Typography.Text>
                </div>
              ))}
            </div>
          )}
          {fNode.conclusion && (
            <div style={{ marginTop: 8 }}>
              <Typography.Text strong>Conclusion: </Typography.Text>
              <Typography.Text code style={{ fontSize: 10 }}>
                {fNode.conclusion}
              </Typography.Text>
            </div>
          )}
          {fNode.metadata && Object.keys(fNode.metadata).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Typography.Text strong>Metadata:</Typography.Text>
              <pre style={{ fontSize: 11, marginTop: 4, color: "#666" }}>
                {JSON.stringify(fNode.metadata, null, 2)}
              </pre>
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <Typography.Text type="secondary">
              Package: {fNode.package_id}
            </Typography.Text>
          </div>
        </div>
      )}
    </Drawer>
  );
}

// ── Main page ──

export function GraphViewer() {
  const [packageId, setPackageId] = useState<string | undefined>();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const { data: packages } = usePackages(1, 100);
  const { data: graphData, isLoading } = useUnifiedGraph(packageId);

  const packageOptions = [
    { value: "", label: "All packages" },
    ...(packages?.items ?? []).map((p) => ({
      value: p.package_id,
      label: p.package_id,
    })),
  ];

  const knowledgeCount = graphData?.knowledge_nodes.length ?? 0;
  const factorCount = graphData?.factor_nodes.length ?? 0;

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Graph
      </Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <Select
            placeholder="Select package"
            style={{ width: 300 }}
            options={packageOptions}
            onChange={(v) => {
              setPackageId(v || undefined);
              setSelectedNode(null);
            }}
            allowClear
          />
          {graphData && (
            <Typography.Text type="secondary">
              {knowledgeCount} nodes &middot; {factorCount} factors
            </Typography.Text>
          )}
        </div>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type}>
              <Tag color={color}>{type}</Tag>
            </span>
          ))}
          <Tag style={{ background: "#595959", color: "#fff", border: "none" }}>factor</Tag>
          <Typography.Text type="secondary">
            solid = premise &middot; dashed = context &middot; arrow = conclusion
          </Typography.Text>
        </div>
      </Card>

      {isLoading && (
        <div style={{ textAlign: "center", padding: 60 }}>
          <Spin size="large" />
        </div>
      )}

      {!isLoading && graphData && (
        <FactorGraphCanvas
          key={packageId ?? "__all__"}
          data={graphData}
          onSelectNode={setSelectedNode}
          useGravity={!packageId}
        />
      )}

      <NodeDetailDrawer
        nodeId={selectedNode}
        data={graphData}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
}
