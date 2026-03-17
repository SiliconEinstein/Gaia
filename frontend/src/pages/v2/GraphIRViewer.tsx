import { useEffect, useRef, useState } from "react";
import { Card, Select, Typography, Spin, Drawer, Tag, Table } from "antd";
import { Network, DataSet } from "vis-network/standalone";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";

// ── Types ──

interface GraphIRPackage {
  slug: string;
  has_raw: boolean;
  has_local: boolean;
  has_parameterization: boolean;
}

interface KnowledgeNode {
  raw_node_id?: string;
  local_canonical_id?: string;
  representative_content?: string;
  knowledge_type: string;
  kind: string | null;
  content?: string;
  parameters?: { name: string; constraint: string }[];
  source_refs?: { package: string; module: string; knowledge_name: string }[];
  member_raw_node_ids?: string[];
  metadata: Record<string, unknown> | null;
}

interface FactorNode {
  factor_id: string;
  type: string;
  premises: string[];
  contexts: string[];
  conclusion: string;
  source_ref: { module: string; knowledge_name: string } | null;
  metadata: Record<string, unknown> | null;
}

interface GraphIR {
  schema_version: string;
  package: string;
  version: string;
  knowledge_nodes: KnowledgeNode[];
  factor_nodes: FactorNode[];
}

interface Parameterization {
  node_priors: Record<string, number>;
  factor_parameters: Record<string, { conditional_probability: number }>;
}

interface Beliefs {
  graph_hash: string;
  node_beliefs: Record<string, number>;
}

// ── API hooks ──

const useGraphIRPackages = () =>
  useQuery({ queryKey: ["graph-ir", "list"], queryFn: () => apiFetch<GraphIRPackage[]>("/graph-ir") });

const useRawGraph = (slug?: string) =>
  useQuery({
    queryKey: ["graph-ir", "raw", slug],
    queryFn: () => apiFetch<GraphIR>(`/graph-ir/${slug}/raw`),
    enabled: !!slug,
  });

const useLocalGraph = (slug?: string) =>
  useQuery({
    queryKey: ["graph-ir", "local", slug],
    queryFn: () => apiFetch<GraphIR>(`/graph-ir/${slug}/local`),
    enabled: !!slug,
  });

const useParameterization = (slug?: string) =>
  useQuery({
    queryKey: ["graph-ir", "params", slug],
    queryFn: () => apiFetch<Parameterization>(`/graph-ir/${slug}/parameterization`),
    enabled: !!slug,
  });

const useBeliefs = (slug?: string) =>
  useQuery({
    queryKey: ["graph-ir", "beliefs", slug],
    queryFn: () => apiFetch<Beliefs>(`/graph-ir/${slug}/beliefs`),
    enabled: !!slug,
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

// ── Vis transform ──

function buildVisGraph(
  localGraph: GraphIR,
  params?: Parameterization,
  beliefs?: Beliefs,
) {
  const nodes: {
    id: string; label: string; title: string;
    color: { background: string; border: string };
    font: { color: string; size: number; multi?: boolean | string };
    shape: string; size: number; borderWidth: number;
  }[] = [];
  const edges: {
    id: string; from: string; to: string;
    arrows: string; color: { color: string }; dashes?: boolean;
    label?: string; font?: { size: number; color: string };
  }[] = [];

  for (const n of localGraph.knowledge_nodes) {
    const nodeId = n.local_canonical_id ?? n.raw_node_id ?? "";
    const name = n.source_refs?.[0]?.knowledge_name ?? nodeId.slice(0, 12);
    const content = n.representative_content ?? n.content ?? "";
    const isSchema = (n.parameters ?? []).length > 0;
    const memberCount = n.member_raw_node_ids?.length ?? 1;
    const isMerged = memberCount > 1;
    const prior = params?.node_priors[nodeId];

    const belief = beliefs?.node_beliefs[nodeId];
    let priorLabel = "";
    if (prior != null && belief != null) {
      const delta = belief - prior;
      const arrow = delta > 0.01 ? "↑" : delta < -0.01 ? "↓" : "=";
      priorLabel = `\n${prior.toFixed(2)} → ${belief.toFixed(2)} ${arrow}`;
    } else if (prior != null) {
      priorLabel = ` [${prior.toFixed(2)}]`;
    }
    const shortName = name.length > 25 ? name.slice(0, 23) + "…" : name;
    const label = `${shortName}${priorLabel}`;

    // Build tooltip
    const lines = [`[${n.knowledge_type}${isSchema ? " schema" : ""}] ${name}`];
    lines.push(content.trim().slice(0, 300));
    if (prior != null) lines.push(`prior: ${prior.toFixed(3)}`);
    if (isMerged) {
      lines.push(`\nMerged from ${memberCount} raw nodes:`);
      for (const rawId of n.member_raw_node_ids ?? []) lines.push(`  • ${rawId}`);
    }
    lines.push(`\nID: ${nodeId}`);

    nodes.push({
      id: nodeId,
      label,
      title: lines.join("\n"),
      color: {
        background: TYPE_COLORS[n.knowledge_type] ?? "#aaa",
        border: isMerged ? "#faad14" : isSchema ? "#faad14" : "#555",
      },
      font: { color: "#fff", size: 10 },
      shape: "box",
      size: 14,
      borderWidth: isSchema || isMerged ? 3 : 1,
    });
  }

  for (const f of localGraph.factor_nodes) {
    const name = f.source_ref?.knowledge_name ?? f.factor_id.slice(0, 10);
    const cp = params?.factor_parameters[f.factor_id]?.conditional_probability;
    const edgeType = (f.metadata?.edge_type as string) ?? f.type;

    const tooltip = [
      `[factor: ${f.type}] ${name}`,
      cp != null ? `conditional_probability: ${cp.toFixed(3)}` : "",
      `premises: ${f.premises.length}, contexts: ${f.contexts.length}`,
      `\nID: ${f.factor_id}`,
    ].filter(Boolean).join("\n");

    nodes.push({
      id: f.factor_id,
      label: edgeType,
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
    edges.push({
      id: `${f.factor_id}->${f.conclusion}`,
      from: f.factor_id,
      to: f.conclusion,
      arrows: "to",
      color: { color: f.type.includes("constraint") ? FACTOR_COLORS[f.type] : "#595959" },
      label: cp != null ? `p=${cp.toFixed(2)}` : undefined,
      font: { size: 9, color: "#888" },
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
      nodeSpacing: 160,
      treeSpacing: 80,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true,
    },
  },
  physics: { enabled: false },
  interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true, dragNodes: true },
  nodes: { borderWidth: 1, borderWidthSelected: 3 },
  edges: {
    smooth: { type: "cubicBezier", forceDirection: "vertical", roundness: 0.3 },
    arrows: { to: { scaleFactor: 0.4 } },
    font: { size: 8, color: "#999" },
    color: { opacity: 0.7 },
  },
};

// ── Components ──

function FactorGraphPanel({
  graph,
  params,
  beliefs,
  onSelectNode,
  height = "70vh",
}: {
  graph: GraphIR | undefined;
  params?: Parameterization;
  beliefs?: Beliefs;
  onSelectNode: (id: string) => void;
  height?: string | number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const onSelectNodeRef = useRef(onSelectNode);
  onSelectNodeRef.current = onSelectNode;

  useEffect(() => {
    if (!containerRef.current || !graph) return;
    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    const { nodes, edges } = buildVisGraph(graph, params, beliefs);
    const net = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet(edges) },
      LAYOUT_OPTIONS,
    );
    net.on("click", (p) => {
      if (p.nodes.length > 0) onSelectNodeRef.current(p.nodes[0] as string);
    });
    networkRef.current = net;
    return () => {
      net.destroy();
      networkRef.current = null;
    };
  }, [graph, params, beliefs]);

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

function NodeDrawer({
  nodeId,
  localGraph,
  rawGraph,
  params,
  beliefs,
  onClose,
}: {
  nodeId: string | null;
  localGraph: GraphIR | undefined;
  rawGraph: GraphIR | undefined;
  params?: Parameterization;
  beliefs?: Beliefs;
  onClose: () => void;
}) {
  if (!nodeId || !localGraph) return null;

  const kNode = localGraph.knowledge_nodes.find(
    (n) => (n.local_canonical_id ?? n.raw_node_id) === nodeId,
  );
  const fNode = localGraph.factor_nodes.find((f) => f.factor_id === nodeId);

  // Find raw members
  const rawMembers = (kNode?.member_raw_node_ids ?? []).map((rawId) => {
    const raw = rawGraph?.knowledge_nodes.find((n) => n.raw_node_id === rawId);
    return {
      raw_node_id: rawId,
      knowledge_name: raw?.source_refs?.[0]?.knowledge_name ?? "?",
      module: raw?.source_refs?.[0]?.module ?? "?",
      content: (raw?.content ?? "").trim().slice(0, 120),
    };
  });

  return (
    <Drawer title="Node Detail" open={!!nodeId} onClose={onClose} width={580}>
      {kNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={TYPE_COLORS[kNode.knowledge_type]}>{kNode.knowledge_type}</Tag>
            {(kNode.parameters ?? []).length > 0 && <Tag color="gold">schema</Tag>}
            {rawMembers.length > 1 && <Tag color="orange">merged ({rawMembers.length})</Tag>}
          </div>
          <Typography.Title level={5}>
            {kNode.source_refs?.[0]?.knowledge_name}
          </Typography.Title>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {nodeId}
          </Typography.Text>
          <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
            {kNode.representative_content ?? kNode.content ?? ""}
          </Typography.Paragraph>
          {params?.node_priors[nodeId] != null && (
            <div style={{ marginTop: 8 }}>
              <Typography.Text strong>Prior: {params.node_priors[nodeId].toFixed(3)}</Typography.Text>
              {beliefs?.node_beliefs[nodeId] != null && (
                <>
                  <Typography.Text strong style={{ marginLeft: 16 }}>
                    Belief: {beliefs.node_beliefs[nodeId].toFixed(3)}
                  </Typography.Text>
                  <Typography.Text
                    style={{ marginLeft: 8 }}
                    type={beliefs.node_beliefs[nodeId] > params.node_priors[nodeId] + 0.01 ? "success" : beliefs.node_beliefs[nodeId] < params.node_priors[nodeId] - 0.01 ? "danger" : "secondary"}
                  >
                    ({(beliefs.node_beliefs[nodeId] - params.node_priors[nodeId] > 0 ? "+" : "")}{(beliefs.node_beliefs[nodeId] - params.node_priors[nodeId]).toFixed(3)})
                  </Typography.Text>
                </>
              )}
            </div>
          )}

          <Typography.Title level={5} style={{ marginTop: 16 }}>
            Raw → Local Canonical Mapping
          </Typography.Title>
          <Table
            size="small"
            pagination={false}
            dataSource={rawMembers}
            rowKey="raw_node_id"
            columns={[
              { title: "Raw ID", dataIndex: "raw_node_id", width: 160,
                render: (v: string) => <Typography.Text code style={{ fontSize: 10 }}>{v}</Typography.Text> },
              { title: "Module", dataIndex: "module", width: 100 },
              { title: "Name", dataIndex: "knowledge_name", width: 140 },
              { title: "Content", dataIndex: "content", ellipsis: true },
            ]}
          />
        </div>
      )}
      {fNode && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Tag color={FACTOR_COLORS[fNode.type]}>{fNode.type}</Tag>
            {fNode.metadata?.edge_type && (
              <Tag>{fNode.metadata.edge_type as string}</Tag>
            )}
          </div>
          <Typography.Title level={5}>
            {fNode.source_ref?.knowledge_name ?? fNode.factor_id}
          </Typography.Title>
          <Typography.Text type="secondary" copyable style={{ fontSize: 11 }}>
            {fNode.factor_id}
          </Typography.Text>
          <div style={{ marginTop: 12 }}>
            <Typography.Text>Premises: {fNode.premises.length}</Typography.Text>
            {fNode.premises.map((p) => (
              <div key={p}><Typography.Text code style={{ fontSize: 10 }}>{p}</Typography.Text></div>
            ))}
          </div>
          {fNode.contexts.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Typography.Text>Contexts: {fNode.contexts.length}</Typography.Text>
              {fNode.contexts.map((c) => (
                <div key={c}><Typography.Text code style={{ fontSize: 10 }}>{c}</Typography.Text></div>
              ))}
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <Typography.Text>Conclusion: </Typography.Text>
            <Typography.Text code style={{ fontSize: 10 }}>{fNode.conclusion}</Typography.Text>
          </div>
          {params?.factor_parameters[fNode.factor_id] && (
            <div style={{ marginTop: 12 }}>
              <Typography.Text strong>
                Conditional probability: {params.factor_parameters[fNode.factor_id].conditional_probability.toFixed(3)}
              </Typography.Text>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

// ── Stats bar ──

function StatsBar({ rawGraph, localGraph, params }: {
  rawGraph?: GraphIR; localGraph?: GraphIR; params?: Parameterization;
}) {
  if (!rawGraph || !localGraph) return null;

  const rawNodes = rawGraph.knowledge_nodes.length;
  const lcnNodes = localGraph.knowledge_nodes.length;
  const merged = rawNodes - lcnNodes;
  const factors = localGraph.factor_nodes.length;
  const reasoningFactors = localGraph.factor_nodes.filter((f) => f.type === "reasoning").length;
  const constraintFactors = localGraph.factor_nodes.filter((f) => f.type.includes("constraint")).length;

  return (
    <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
      <span>
        <Typography.Text strong>{rawNodes}</Typography.Text>
        <Typography.Text type="secondary"> raw nodes</Typography.Text>
        {merged > 0 && (
          <>
            <Typography.Text type="secondary"> → </Typography.Text>
            <Typography.Text strong style={{ color: "#faad14" }}>{lcnNodes}</Typography.Text>
            <Typography.Text type="secondary"> canonical ({merged} merged)</Typography.Text>
          </>
        )}
        {merged === 0 && (
          <Typography.Text type="secondary"> → {lcnNodes} canonical (1:1)</Typography.Text>
        )}
      </span>
      <span>
        <Typography.Text strong>{factors}</Typography.Text>
        <Typography.Text type="secondary"> factors ({reasoningFactors} reasoning, {constraintFactors} constraint)</Typography.Text>
      </span>
      {params && (
        <span>
          <Typography.Text strong>{Object.keys(params.node_priors).length}</Typography.Text>
          <Typography.Text type="secondary"> priors</Typography.Text>
        </span>
      )}
    </div>
  );
}

// ── Main page ──

export function GraphIRViewer() {
  const [slug, setSlug] = useState<string | undefined>();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const { data: packages } = useGraphIRPackages();
  const { data: rawGraph } = useRawGraph(slug);
  const { data: localGraph, isLoading } = useLocalGraph(slug);
  const { data: params } = useParameterization(slug);
  const { data: beliefs } = useBeliefs(slug);

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Graph IR Viewer
      </Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <Select
            placeholder="Select package"
            style={{ width: 300 }}
            options={(packages ?? []).map((p) => ({ value: p.slug, label: p.slug }))}
            onChange={(v) => { setSlug(v); setSelectedNode(null); }}
          />
          {rawGraph && localGraph && (
            <StatsBar rawGraph={rawGraph} localGraph={localGraph} params={params} />
          )}
        </div>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type}><Tag color={color}>{type}</Tag></span>
          ))}
          <Tag style={{ background: "#595959", color: "#fff", border: "none" }}>● factor</Tag>
          <Typography.Text type="secondary">solid = premise · dashed = context · thick gold border = schema/merged</Typography.Text>
        </div>
      </Card>

      {isLoading && (
        <div style={{ textAlign: "center", padding: 60 }}><Spin size="large" /></div>
      )}

      {!isLoading && slug && localGraph && (
        <FactorGraphPanel
          key={slug}
          graph={localGraph}
          params={params}
          beliefs={beliefs}
          onSelectNode={setSelectedNode}
        />
      )}

      <NodeDrawer
        nodeId={selectedNode}
        localGraph={localGraph}
        rawGraph={rawGraph}
        params={params}
        beliefs={beliefs}
        onClose={() => setSelectedNode(null)}
      />
    </div>
  );
}
