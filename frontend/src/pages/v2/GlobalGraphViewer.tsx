import { useEffect, useRef, useState } from "react";
import { Card, Typography, Spin, Drawer, Tag, Table } from "antd";
import { Network, DataSet } from "vis-network/standalone";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";

// ── Types ──

interface GlobalNode {
  global_canonical_id: string;
  knowledge_type: string;
  kind: string | null;
  representative_content: string;
  parameters?: { name: string; constraint: string }[];
  member_local_nodes?: { package: string; version: string; local_canonical_id: string }[];
  provenance?: { package: string; version: string }[];
  metadata: Record<string, unknown> | null;
}

interface FactorNode {
  factor_id: string;
  type: string;
  premises: string[];
  contexts: string[];
  conclusion: string;
  source_ref: { package: string; module: string; knowledge_name: string } | null;
  metadata: Record<string, unknown> | null;
}

interface GlobalGraph {
  schema_version: string;
  knowledge_nodes: GlobalNode[];
  factor_nodes: FactorNode[];
  bindings: { package: string; local_canonical_id: string; decision: string; global_canonical_id: string; reason: string | null }[];
}

// ── API ──

const useGlobalGraph = () =>
  useQuery({
    queryKey: ["graph-ir", "global"],
    queryFn: () => apiFetch<GlobalGraph>("/graph-ir/global"),
  });

// ── Colors ──

const TYPE_COLORS: Record<string, string> = {
  claim: "#1677ff",
  setting: "#52c41a",
  question: "#fa8c16",
  action: "#722ed1",
  contradiction: "#f5222d",
  equivalence: "#13c2c2",
};

const FACTOR_COLORS: Record<string, string> = {
  reasoning: "#595959",
  instantiation: "#8c8c8c",
  mutex_constraint: "#cf1322",
  equiv_constraint: "#08979c",
};

const PACKAGE_COLORS: Record<string, string> = {};
const PALETTE = ["#1677ff", "#52c41a", "#fa8c16", "#722ed1", "#f5222d", "#13c2c2", "#eb2f96", "#faad14"];

function getPackageColor(pkg: string): string {
  if (!PACKAGE_COLORS[pkg]) {
    PACKAGE_COLORS[pkg] = PALETTE[Object.keys(PACKAGE_COLORS).length % PALETTE.length];
  }
  return PACKAGE_COLORS[pkg];
}

// ── Vis transform ──

function buildVisGraph(graph: GlobalGraph) {
  const nodes: {
    id: string; label: string; title: string;
    color: { background: string; border: string };
    font: { color: string; size: number };
    shape: string; size: number; borderWidth: number;
  }[] = [];
  const edges: {
    id: string; from: string; to: string;
    arrows: string; color: { color: string }; dashes?: boolean;
    label?: string; font?: { size: number; color: string };
  }[] = [];

  for (const n of graph.knowledge_nodes) {
    const nodeId = n.global_canonical_id;
    const meta = (n.metadata ?? {}) as Record<string, unknown>;
    const sourceNames = Array.isArray(meta.source_knowledge_names) ? meta.source_knowledge_names as string[] : [];
    const shortName = sourceNames[0]?.split(".")?.[1] ?? nodeId.slice(4, 16);
    const pkgs = (n.provenance ?? []).map((p) => p.package);
    const isMultiPkg = pkgs.length > 1;
    const borderColor = isMultiPkg ? "#faad14" : pkgs[0] ? getPackageColor(pkgs[0]) : "#333";

    // Beliefs from GlobalInferenceState
    const prior = graph.inference_state?.node_priors?.[nodeId];
    const belief = graph.inference_state?.node_beliefs?.[nodeId];
    let beliefLabel = "";
    if (prior != null && belief != null) {
      const delta = belief - prior;
      const arrow = delta > 0.01 ? "↑" : delta < -0.01 ? "↓" : "=";
      beliefLabel = `\n${prior.toFixed(2)} → ${belief.toFixed(2)} ${arrow}`;
    }

    const truncName = shortName.length > 25 ? shortName.slice(0, 23) + "..." : shortName;
    const label = `${truncName}${beliefLabel}`;

    const tooltip = [
      `[${n.knowledge_type}] ${shortName}`,
      n.representative_content.trim().slice(0, 200),
      prior != null ? `prior: ${prior.toFixed(3)}` : "",
      belief != null ? `belief: ${belief.toFixed(3)}` : "",
      `Packages: ${pkgs.join(", ")}`,
      `Members: ${n.member_local_nodes?.length ?? 0}`,
      `ID: ${nodeId}`,
    ].filter(Boolean).join("\n");

    nodes.push({
      id: nodeId,
      label,
      title: tooltip,
      color: {
        background: TYPE_COLORS[n.knowledge_type] ?? "#aaa",
        border: borderColor,
      },
      font: { color: "#fff", size: 10 },
      shape: "box",
      size: 14,
      borderWidth: isMultiPkg ? 4 : 2,
    });
  }

  for (const f of graph.factor_nodes) {
    const edgeType = (f.metadata?.edge_type as string) ?? f.type;
    const srcPkg = f.source_ref?.package ?? "";

    nodes.push({
      id: f.factor_id,
      label: edgeType,
      title: `[factor: ${f.type}] ${f.source_ref?.knowledge_name ?? f.factor_id}\nPackage: ${srcPkg}\nPremises: ${f.premises.length}`,
      color: {
        background: FACTOR_COLORS[f.type] ?? "#595959",
        border: srcPkg ? getPackageColor(srcPkg) : "#333",
      },
      font: { color: "#fff", size: 8 },
      shape: "box",
      size: 6,
      borderWidth: 1,
    });

    for (let pi = 0; pi < f.premises.length; pi++) {
      edges.push({
        id: `${f.factor_id}:p${pi}:${f.premises[pi]}`,
        from: f.premises[pi],
        to: f.factor_id,
        arrows: "",
        color: { color: "#595959" },
      });
    }
    edges.push({
      id: `${f.factor_id}:conclusion`,
      from: f.factor_id,
      to: f.conclusion,
      arrows: "to",
      color: { color: f.type.includes("constraint") ? FACTOR_COLORS[f.type] : "#595959" },
    });
  }

  return { nodes, edges };
}

const LAYOUT_OPTIONS = {
  layout: {
    hierarchical: {
      enabled: true,
      direction: "UD",
      sortMethod: "directed",
      levelSeparation: 50,
      nodeSpacing: 150,
      treeSpacing: 80,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true,
    },
  },
  physics: { enabled: false },
  interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true, dragNodes: true },
  nodes: { borderWidth: 2, borderWidthSelected: 3 },
  edges: {
    smooth: { type: "cubicBezier", forceDirection: "vertical", roundness: 0.3 },
    arrows: { to: { scaleFactor: 0.4 } },
    font: { size: 8, color: "#999" },
    color: { opacity: 0.7 },
  },
};

// ── Components ──

function GraphPanel({
  graph,
  onSelectNode,
}: {
  graph: GlobalGraph;
  onSelectNode: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const cbRef = useRef(onSelectNode);
  cbRef.current = onSelectNode;

  useEffect(() => {
    if (!containerRef.current) return;
    if (networkRef.current) { networkRef.current.destroy(); networkRef.current = null; }

    const { nodes, edges } = buildVisGraph(graph);
    const net = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet(edges) },
      LAYOUT_OPTIONS,
    );
    net.on("click", (p) => {
      if (p.nodes.length > 0) cbRef.current(p.nodes[0] as string);
    });
    networkRef.current = net;
    return () => { net.destroy(); networkRef.current = null; };
  }, [graph]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "70vh", minHeight: 400, border: "1px solid #e8e8e8", borderRadius: 6, background: "#fafafa" }}
    />
  );
}

function NodeDrawer({
  nodeId,
  graph,
  onClose,
}: {
  nodeId: string | null;
  graph: GlobalGraph | undefined;
  onClose: () => void;
}) {
  if (!nodeId || !graph) return null;

  const kNode = graph.knowledge_nodes.find((n) => n.global_canonical_id === nodeId);
  const fNode = graph.factor_nodes.find((f) => f.factor_id === nodeId);

  return (
    <Drawer title="Node Detail" open={!!nodeId} onClose={onClose} width={600}>
      {kNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={TYPE_COLORS[kNode.knowledge_type]}>{kNode.knowledge_type}</Tag>
            {(kNode.provenance ?? []).map((p) => (
              <Tag key={p.package} color={getPackageColor(p.package)}>{p.package}</Tag>
            ))}
            {(kNode.member_local_nodes ?? []).length > 1 && (
              <Tag color="orange">merged ({kNode.member_local_nodes?.length})</Tag>
            )}
          </div>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {nodeId}
          </Typography.Text>
          <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
            {kNode.representative_content}
          </Typography.Paragraph>
          {(() => {
            const p = graph.inference_state?.node_priors?.[nodeId];
            const b = graph.inference_state?.node_beliefs?.[nodeId];
            if (p == null) return null;
            return (
              <div style={{ marginTop: 8 }}>
                <Typography.Text strong>Prior: {p.toFixed(3)}</Typography.Text>
                {b != null && (
                  <>
                    <Typography.Text strong style={{ marginLeft: 16 }}>
                      Belief: {b.toFixed(3)}
                    </Typography.Text>
                    <Typography.Text
                      style={{ marginLeft: 8 }}
                      type={b > p + 0.01 ? "success" : b < p - 0.01 ? "danger" : "secondary"}
                    >
                      ({(b - p > 0 ? "+" : "")}{(b - p).toFixed(3)})
                    </Typography.Text>
                  </>
                )}
              </div>
            );
          })()}

          <Typography.Title level={5} style={{ marginTop: 16 }}>
            Member Local Nodes
          </Typography.Title>
          <Table
            size="small"
            pagination={false}
            dataSource={kNode.member_local_nodes ?? []}
            rowKey="local_canonical_id"
            columns={[
              { title: "Package", dataIndex: "package", width: 160 },
              { title: "Version", dataIndex: "version", width: 80 },
              { title: "Local ID", dataIndex: "local_canonical_id",
                render: (v: string) => <Typography.Text code style={{ fontSize: 10 }}>{v}</Typography.Text> },
            ]}
          />

          {Array.isArray((kNode.metadata as Record<string, unknown>)?.source_knowledge_names) && (
            <div style={{ marginTop: 12 }}>
              <Typography.Text type="secondary">
                Sources: {((kNode.metadata as Record<string, unknown>).source_knowledge_names as string[]).join(", ")}
              </Typography.Text>
            </div>
          )}
        </div>
      )}
      {fNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={FACTOR_COLORS[fNode.type]}>{fNode.type}</Tag>
            {fNode.metadata?.edge_type && <Tag>{fNode.metadata.edge_type as string}</Tag>}
            {fNode.source_ref && <Tag color={getPackageColor(fNode.source_ref.package)}>{fNode.source_ref.package}</Tag>}
          </div>
          <Typography.Title level={5}>
            {fNode.source_ref?.knowledge_name ?? fNode.factor_id}
          </Typography.Title>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {fNode.factor_id}
          </Typography.Text>
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong>Premises ({fNode.premises.length}):</Typography.Text>
            {fNode.premises.map((p) => (
              <div key={p}><Typography.Text code style={{ fontSize: 10 }}>{p}</Typography.Text></div>
            ))}
          </div>
          <div style={{ marginTop: 8 }}>
            <Typography.Text strong>Conclusion: </Typography.Text>
            <Typography.Text code style={{ fontSize: 10 }}>{fNode.conclusion}</Typography.Text>
          </div>
        </div>
      )}
    </Drawer>
  );
}

// ── Main ──

export function GlobalGraphViewer() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const { data: graph, isLoading } = useGlobalGraph();

  const packages = graph ? [...new Set(graph.bindings.map((b) => b.package))] : [];
  const crossFactors = graph ? graph.factor_nodes.filter((f) => {
    const srcPkg = f.source_ref?.package;
    return f.premises.some((p) => {
      const node = graph.knowledge_nodes.find((n) => n.global_canonical_id === p);
      return node && node.provenance?.some((pr) => pr.package !== srcPkg);
    });
  }).length : 0;

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Global Graph
      </Typography.Title>

      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type}><Tag color={color}>{type}</Tag></span>
          ))}
          <Tag style={{ background: "#595959", color: "#fff", border: "none" }}>factor</Tag>
          <Typography.Text type="secondary">
            border color = source package · thick gold = multi-package
          </Typography.Text>
        </div>
      </Card>

      {graph && (
        <Card size="small" style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <span>
              <Typography.Text strong>{graph.knowledge_nodes.length}</Typography.Text>
              <Typography.Text type="secondary"> nodes</Typography.Text>
            </span>
            <span>
              <Typography.Text strong>{graph.factor_nodes.length}</Typography.Text>
              <Typography.Text type="secondary"> factors</Typography.Text>
            </span>
            <span>
              <Typography.Text strong>{crossFactors}</Typography.Text>
              <Typography.Text type="secondary"> cross-package</Typography.Text>
            </span>
            <span>
              <Typography.Text strong>{graph.bindings.length}</Typography.Text>
              <Typography.Text type="secondary"> bindings</Typography.Text>
            </span>
            <span>
              {packages.map((pkg) => (
                <Tag key={pkg} color={getPackageColor(pkg)}>{pkg}</Tag>
              ))}
            </span>
          </div>
        </Card>
      )}

      {isLoading && (
        <div style={{ textAlign: "center", padding: 60 }}><Spin size="large" /></div>
      )}

      {!isLoading && graph && (
        <GraphPanel graph={graph} onSelectNode={setSelectedNode} />
      )}

      <NodeDrawer nodeId={selectedNode} graph={graph} onClose={() => setSelectedNode(null)} />
    </div>
  );
}
