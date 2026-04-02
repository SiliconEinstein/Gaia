import { useEffect, useRef, useState, useCallback } from "react";
import { Spin, Card, Select, Space, Row, Col, Statistic, Drawer, Descriptions, Tag, Button, List } from "antd";
import { ZoomInOutlined, ZoomOutOutlined, ExpandOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import dagre from "dagre";

interface GraphNode {
  id: string;
  type: "variable" | "factor";
  subtype: string;
  label: string;
  content?: string;
  prior?: number | null;
  factor_type?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: "premise" | "conclusion";
}

interface GraphData {
  package_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface Package {
  package_id: string;
  variable_count: number;
}

const VAR_STYLES: Record<string, { fill: string; stroke: string; dash?: boolean }> = {
  claim: { fill: "#f0f0f0", stroke: "#666" },
  setting: { fill: "#e6f7e6", stroke: "#52c41a" },
  question: { fill: "#fff7e6", stroke: "#faad14", dash: true },
};

const FACTOR_SYMBOLS: Record<string, string> = {
  noisy_and: "∧",
  infer: "→",
  contradiction: "⊗",
  deduction: "⊢",
  equivalence: "≡",
  implication: "⇒",
};

export default function GraphPage() {
  const [packages, setPackages] = useState<Package[]>([]);
  const [selectedPkg, setSelectedPkg] = useState<string | undefined>();
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, startTx: 0, startTy: 0 });

  useEffect(() => {
    fetch("/api/packages")
      .then((r) => r.json())
      .then((pkgs: Package[]) => {
        setPackages(pkgs);
        if (pkgs.length > 0) setSelectedPkg(pkgs[0].package_id);
      });
  }, []);

  useEffect(() => {
    if (!selectedPkg) return;
    setLoading(true);
    fetch(`/api/graph/local/${encodeURIComponent(selectedPkg)}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [selectedPkg]);

  useEffect(() => {
    if (!data || !svgRef.current) return;
    transformRef.current = { x: 0, y: 0, scale: 1 };
    renderGraph(data, svgRef.current, handleNodeClick);
    applyTransform();
  }, [data]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setDrawerOpen(true);
  }, []);

  const applyTransform = useCallback(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const g = svg.querySelector("#graph-content") as SVGGElement;
    if (!g) return;
    const { x, y, scale } = transformRef.current;
    g.setAttribute("transform", `translate(${x},${y}) scale(${scale})`);
  }, []);

  const zoom = useCallback((delta: number) => {
    const t = transformRef.current;
    t.scale = Math.max(0.2, Math.min(3, t.scale + delta));
    applyTransform();
  }, [applyTransform]);

  const resetView = useCallback(() => {
    transformRef.current = { x: 0, y: 0, scale: 1 };
    applyTransform();
  }, [applyTransform]);

  // Wheel zoom
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      zoom(delta);
    };
    container.addEventListener("wheel", handler, { passive: false });
    return () => container.removeEventListener("wheel", handler);
  }, [zoom]);

  // Pan drag
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onDown = (e: MouseEvent) => {
      if ((e.target as Element)?.closest(".graph-node")) return; // Don't drag when clicking nodes
      dragRef.current = {
        dragging: true,
        startX: e.clientX,
        startY: e.clientY,
        startTx: transformRef.current.x,
        startTy: transformRef.current.y,
      };
    };
    const onMove = (e: MouseEvent) => {
      const d = dragRef.current;
      if (!d.dragging) return;
      transformRef.current.x = d.startTx + (e.clientX - d.startX);
      transformRef.current.y = d.startTy + (e.clientY - d.startY);
      applyTransform();
    };
    const onUp = () => { dragRef.current.dragging = false; };

    container.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      container.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [applyTransform]);

  const varNodes = data?.nodes.filter((n) => n.type === "variable") ?? [];
  const facNodes = data?.nodes.filter((n) => n.type === "factor") ?? [];

  // Find connected edges for selected node
  const connectedEdges = selectedNode && data
    ? data.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
    : [];
  const connectedNodeIds = new Set(connectedEdges.flatMap((e) => [e.source, e.target]));
  connectedNodeIds.delete(selectedNode?.id ?? "");
  const connectedNodes = data?.nodes.filter((n) => connectedNodeIds.has(n.id)) ?? [];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <span>Package:</span>
        <Select
          style={{ width: 350 }}
          value={selectedPkg}
          onChange={setSelectedPkg}
          options={packages.map((p) => ({
            value: p.package_id,
            label: `${p.package_id} (${p.variable_count} vars)`,
          }))}
        />
        <Button icon={<ZoomInOutlined />} onClick={() => zoom(0.2)} />
        <Button icon={<ZoomOutOutlined />} onClick={() => zoom(-0.2)} />
        <Button icon={<ExpandOutlined />} onClick={resetView}>Reset</Button>
      </Space>

      {data && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small"><Statistic title="Variables" value={varNodes.length} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small"><Statistic title="Factors" value={facNodes.length} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small"><Statistic title="Edges" value={data.edges.length} /></Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
                {Object.entries(VAR_STYLES).map(([k, s]) => (
                  <span key={k}>
                    <span style={{ display: "inline-block", width: 12, height: 12, backgroundColor: s.fill, border: `2px ${s.dash ? "dashed" : "solid"} ${s.stroke}`, marginRight: 4 }} />
                    {k}
                  </span>
                ))}
                <span>
                  <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", backgroundColor: "#e0e0e0", border: "2px solid #999", marginRight: 4 }} />
                  factor
                </span>
              </div>
            </Card>
          </Col>
        </Row>
      )}

      {loading ? (
        <Spin size="large" />
      ) : (
        <Card style={{ overflow: "hidden", cursor: "grab" }} ref={containerRef}>
          <svg ref={svgRef} width="100%" height="700" />
        </Card>
      )}

      <Drawer
        title={selectedNode ? (selectedNode.type === "variable" ? "Variable Detail" : "Factor Detail") : ""}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={500}
      >
        {selectedNode && selectedNode.type === "variable" && (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="ID"><code>{selectedNode.id}</code></Descriptions.Item>
              <Descriptions.Item label="Type"><Tag>{selectedNode.subtype}</Tag></Descriptions.Item>
              <Descriptions.Item label="Content">{selectedNode.content}</Descriptions.Item>
              {selectedNode.prior != null && (
                <Descriptions.Item label="Prior">{selectedNode.prior.toFixed(3)}</Descriptions.Item>
              )}
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <Link to={`/variables/${encodeURIComponent(selectedNode.id)}`}>
                <Button type="link">View in Variables table →</Button>
              </Link>
            </div>
          </>
        )}
        {selectedNode && selectedNode.type === "factor" && (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="ID"><code>{selectedNode.id}</code></Descriptions.Item>
              <Descriptions.Item label="Type"><Tag>{selectedNode.factor_type}</Tag></Descriptions.Item>
              <Descriptions.Item label="Subtype"><Tag>{selectedNode.subtype}</Tag></Descriptions.Item>
            </Descriptions>
          </>
        )}
        {connectedNodes.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>Connected Nodes</h4>
            <List
              size="small"
              dataSource={connectedNodes}
              renderItem={(n) => {
                const edge = connectedEdges.find((e) => e.source === n.id || e.target === n.id);
                const role = edge?.source === selectedNode?.id ? "→ output" : "← input";
                return (
                  <List.Item>
                    <Tag color={n.type === "variable" ? "blue" : "purple"}>{n.type}</Tag>
                    <span style={{ flex: 1 }}>
                      {n.type === "variable" ? n.label : `[${n.subtype}]`}
                    </span>
                    <Tag>{role}</Tag>
                  </List.Item>
                );
              }}
            />
          </div>
        )}
      </Drawer>
    </>
  );
}

function renderGraph(
  data: GraphData,
  svg: SVGSVGElement,
  onNodeClick: (node: GraphNode) => void,
) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 40, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  const nodeMap = new Map<string, GraphNode>();
  for (const node of data.nodes) {
    nodeMap.set(node.id, node);
    if (node.type === "variable") {
      g.setNode(node.id, { width: 180, height: 50 });
    } else {
      g.setNode(node.id, { width: 30, height: 30 });
    }
  }

  for (const edge of data.edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  let maxX = 0, maxY = 0;
  g.nodes().forEach((id) => {
    const n = g.node(id);
    if (n) {
      maxX = Math.max(maxX, n.x + n.width / 2);
      maxY = Math.max(maxY, n.y + n.height / 2);
    }
  });

  svg.innerHTML = "";

  // Defs
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", "arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "10");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "8");
  marker.setAttribute("markerHeight", "8");
  marker.setAttribute("orient", "auto");
  const arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  arrowPath.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  arrowPath.setAttribute("fill", "#999");
  marker.appendChild(arrowPath);
  defs.appendChild(marker);
  svg.appendChild(defs);

  // Content group (for zoom/pan)
  const contentGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
  contentGroup.setAttribute("id", "graph-content");

  // Edges
  g.edges().forEach((e) => {
    const edge = g.edge(e);
    if (!edge?.points) return;
    const pathStr = edge.points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute("d", pathStr);
    line.setAttribute("stroke", "#999");
    line.setAttribute("stroke-width", "1.5");
    line.setAttribute("fill", "none");
    line.setAttribute("marker-end", "url(#arrow)");
    contentGroup.appendChild(line);
  });

  // Nodes
  g.nodes().forEach((id) => {
    const layout = g.node(id);
    const node = nodeMap.get(id);
    if (!layout || !node) return;

    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("transform", `translate(${layout.x}, ${layout.y})`);
    group.setAttribute("class", "graph-node");
    group.style.cursor = "pointer";
    group.addEventListener("click", (e) => {
      e.stopPropagation();
      onNodeClick(node);
    });

    if (node.type === "variable") {
      const style = VAR_STYLES[node.subtype] || VAR_STYLES.claim;
      const w = layout.width, h = layout.height;

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(-w / 2));
      rect.setAttribute("y", String(-h / 2));
      rect.setAttribute("width", String(w));
      rect.setAttribute("height", String(h));
      rect.setAttribute("rx", "4");
      rect.setAttribute("fill", style.fill);
      rect.setAttribute("stroke", style.stroke);
      rect.setAttribute("stroke-width", "2");
      if (style.dash) rect.setAttribute("stroke-dasharray", "6,3");
      group.appendChild(rect);

      // Hover highlight
      group.addEventListener("mouseenter", () => rect.setAttribute("stroke-width", "3"));
      group.addEventListener("mouseleave", () => rect.setAttribute("stroke-width", "2"));

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("y", node.prior != null ? "-4" : "4");
      label.setAttribute("font-size", "11");
      label.setAttribute("font-family", "system-ui, sans-serif");
      label.textContent = node.label.length > 22 ? node.label.slice(0, 20) + "…" : node.label;
      group.appendChild(label);

      if (node.prior != null) {
        const val = document.createElementNS("http://www.w3.org/2000/svg", "text");
        val.setAttribute("text-anchor", "middle");
        val.setAttribute("y", "14");
        val.setAttribute("font-size", "10");
        val.setAttribute("fill", "#888");
        val.textContent = `p = ${node.prior.toFixed(3)}`;
        group.appendChild(val);
      }
    } else {
      const r = 14;
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", String(r));
      const isCont = node.subtype === "contradiction";
      circle.setAttribute("fill", isCont ? "#fff0f0" : "#e8e8e8");
      circle.setAttribute("stroke", isCont ? "#ff4d4f" : "#999");
      circle.setAttribute("stroke-width", "2");
      group.appendChild(circle);

      group.addEventListener("mouseenter", () => circle.setAttribute("stroke-width", "3"));
      group.addEventListener("mouseleave", () => circle.setAttribute("stroke-width", "2"));

      const sym = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sym.setAttribute("text-anchor", "middle");
      sym.setAttribute("y", "5");
      sym.setAttribute("font-size", "14");
      sym.setAttribute("font-weight", "bold");
      sym.setAttribute("fill", isCont ? "#ff4d4f" : "#666");
      sym.textContent = FACTOR_SYMBOLS[node.subtype] || "f";
      group.appendChild(sym);
    }

    contentGroup.appendChild(group);
  });

  svg.appendChild(contentGroup);
}
