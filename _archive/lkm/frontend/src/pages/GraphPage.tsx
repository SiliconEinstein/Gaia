import { useEffect, useRef, useState, useCallback } from "react";
import {
  Spin,
  Card,
  Select,
  Space,
  Row,
  Col,
  Statistic,
  Descriptions,
  Tag,
  Button,
  List,
} from "antd";
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  ExpandOutlined,
  CloseOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import dagre from "dagre";

interface GraphNode {
  id: string;
  type: "variable" | "factor";
  subtype: string;
  label: string;
  content?: string;
  prior?: number | null;
  gcn_id?: string;
  factor_type?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: "premise" | "conclusion" | "background";
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

const VAR_STYLES: Record<
  string,
  { fill: string; stroke: string; dash?: boolean }
> = {
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
  const svgRef = useRef<SVGSVGElement>(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const dragRef = useRef({
    active: false,
    startX: 0,
    startY: 0,
    startTx: 0,
    startTy: 0,
  });

  useEffect(() => {
    fetch("/api/packages?limit=20")
      .then((r) => r.json())
      .then((resp: { items: Package[]; total: number }) => {
        setPackages(resp.items);
        if (resp.items.length > 0) setSelectedPkg(resp.items[0].package_id);
      });
  }, []);

  useEffect(() => {
    if (!selectedPkg) return;
    setLoading(true);
    setSelectedNode(null);
    fetch(`/api/graph/local/${encodeURIComponent(selectedPkg)}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [selectedPkg]);

  useEffect(() => {
    if (!data || !svgRef.current) return;
    transformRef.current = { x: 0, y: 0, scale: 1 };
    renderGraph(data, svgRef.current, (node) => setSelectedNode(node));
    applyTransform();
  }, [data]);

  const applyTransform = useCallback(() => {
    const g = svgRef.current?.querySelector("#graph-content") as SVGGElement;
    if (!g) return;
    const { x, y, scale } = transformRef.current;
    g.setAttribute("transform", `translate(${x},${y}) scale(${scale})`);
  }, []);

  const zoom = useCallback(
    (delta: number) => {
      transformRef.current.scale = Math.max(
        0.2,
        Math.min(3, transformRef.current.scale + delta)
      );
      applyTransform();
    },
    [applyTransform]
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.stopPropagation();
      zoom(e.deltaY > 0 ? -0.1 : 0.1);
    },
    [zoom]
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as Element)?.closest(".graph-node")) return;
    // Clicked on background: close detail panel
    setSelectedNode(null);
    e.preventDefault();
    dragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startTx: transformRef.current.x,
      startTy: transformRef.current.y,
    };
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current.active) return;
      transformRef.current.x =
        dragRef.current.startTx + (e.clientX - dragRef.current.startX);
      transformRef.current.y =
        dragRef.current.startTy + (e.clientY - dragRef.current.startY);
      applyTransform();
    };
    const onUp = () => {
      dragRef.current.active = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [applyTransform]);

  const varNodes = data?.nodes.filter((n) => n.type === "variable") ?? [];
  const facNodes = data?.nodes.filter((n) => n.type === "factor") ?? [];

  const connectedEdges =
    selectedNode && data
      ? data.edges.filter(
          (e) => e.source === selectedNode.id || e.target === selectedNode.id
        )
      : [];
  const connectedNodeIds = new Set(
    connectedEdges.flatMap((e) => [e.source, e.target])
  );
  connectedNodeIds.delete(selectedNode?.id ?? "");
  const connectedNodes =
    data?.nodes.filter((n) => connectedNodeIds.has(n.id)) ?? [];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <span>Package:</span>
        <Select
          showSearch
          style={{ width: 400 }}
          value={selectedPkg}
          onChange={setSelectedPkg}
          filterOption={false}
          onSearch={(val) => {
            const params = new URLSearchParams({ limit: "20" });
            if (val) params.set("q", val);
            fetch(`/api/packages?${params}`)
              .then((r) => r.json())
              .then((resp: { items: Package[]; total: number }) =>
                setPackages(resp.items)
              );
          }}
          options={packages.map((p) => ({
            value: p.package_id,
            label: `${p.package_id} (${p.variable_count} vars)`,
          }))}
          placeholder="Search packages..."
        />
      </Space>

      {data && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic title="Variables" value={varNodes.length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="Factors" value={facNodes.length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="Edges" value={data.edges.length} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  flexWrap: "wrap",
                  fontSize: 12,
                }}
              >
                {Object.entries(VAR_STYLES).map(([k, s]) => (
                  <span key={k}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: 12,
                        backgroundColor: s.fill,
                        border: `2px ${s.dash ? "dashed" : "solid"} ${s.stroke}`,
                        marginRight: 4,
                      }}
                    />
                    {k}
                  </span>
                ))}
                <span>
                  <span
                    style={{
                      display: "inline-block",
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      backgroundColor: "#e0e0e0",
                      border: "2px solid #999",
                      marginRight: 4,
                    }}
                  />
                  factor
                </span>
                <span>
                  <span
                    style={{
                      display: "inline-block",
                      width: 20,
                      borderTop: "2px dashed #52c41a",
                      marginRight: 4,
                      verticalAlign: "middle",
                    }}
                  />
                  background
                </span>
              </div>
            </Card>
          </Col>
        </Row>
      )}

      {loading ? (
        <Spin size="large" />
      ) : (
        <div style={{ display: "flex", gap: 16 }}>
          {/* Graph */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              position: "relative",
              border: "1px solid #f0f0f0",
              borderRadius: 8,
              overflow: "hidden",
              background: "#fafafa",
            }}
          >
            <svg
              ref={svgRef}
              width="100%"
              height="700"
              style={{ cursor: dragRef.current.active ? "grabbing" : "grab" }}
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
            />
            {/* Floating zoom controls */}
            <div
              style={{
                position: "absolute",
                top: 12,
                right: 12,
                display: "flex",
                gap: 4,
                background: "rgba(255,255,255,0.9)",
                borderRadius: 6,
                padding: 4,
                boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
              }}
            >
              <Button
                size="small"
                icon={<ZoomInOutlined />}
                onClick={() => zoom(0.2)}
              />
              <Button
                size="small"
                icon={<ZoomOutOutlined />}
                onClick={() => zoom(-0.2)}
              />
              <Button
                size="small"
                icon={<ExpandOutlined />}
                onClick={() => {
                  transformRef.current = { x: 0, y: 0, scale: 1 };
                  applyTransform();
                }}
              />
            </div>
          </div>

          {/* Detail panel */}
          {selectedNode && (
            <div
              style={{
                width: 360,
                flexShrink: 0,
                border: "1px solid #f0f0f0",
                borderRadius: 8,
                padding: 16,
                background: "#fff",
                overflowY: "auto",
                maxHeight: 700,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <h4 style={{ margin: 0 }}>
                  {selectedNode.type === "variable" ? "Variable" : "Factor"}
                </h4>
                <Button
                  type="text"
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={() => setSelectedNode(null)}
                />
              </div>

              {selectedNode.type === "variable" && (
                <>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="Label">
                      <strong>{selectedNode.label}</strong>
                    </Descriptions.Item>
                    <Descriptions.Item label="Type">
                      <Tag>{selectedNode.subtype}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Content">
                      {selectedNode.content}
                    </Descriptions.Item>
                    {selectedNode.prior != null && (
                      <Descriptions.Item label="Prior">
                        {selectedNode.prior.toFixed(3)}
                      </Descriptions.Item>
                    )}
                    <Descriptions.Item label="QID">
                      <code
                        style={{ fontSize: 10, wordBreak: "break-all" }}
                      >
                        {selectedNode.id}
                      </code>
                    </Descriptions.Item>
                  </Descriptions>
                  {selectedNode.gcn_id && (
                    <div style={{ marginTop: 12 }}>
                      <Link
                        to={`/variables/${encodeURIComponent(selectedNode.gcn_id)}`}
                      >
                        <Button type="primary" size="small" block>
                          View global detail →
                        </Button>
                      </Link>
                    </div>
                  )}
                </>
              )}

              {selectedNode.type === "factor" && (
                <Descriptions column={1} bordered size="small">
                  <Descriptions.Item label="ID">
                    <code style={{ fontSize: 10 }}>{selectedNode.id}</code>
                  </Descriptions.Item>
                  <Descriptions.Item label="Type">
                    <Tag>{selectedNode.factor_type}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Subtype">
                    <Tag>{selectedNode.subtype}</Tag>
                  </Descriptions.Item>
                </Descriptions>
              )}

              {connectedNodes.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ marginBottom: 8 }}>
                    Connected ({connectedNodes.length})
                  </h4>
                  <List
                    size="small"
                    dataSource={connectedNodes}
                    renderItem={(n) => {
                      const edge = connectedEdges.find(
                        (e) => e.source === n.id || e.target === n.id
                      );
                      const edgeType = edge?.type ?? "";
                      const isInput = edge?.target === selectedNode?.id;
                      return (
                        <List.Item style={{ padding: "4px 0" }}>
                          <Tag
                            color={
                              n.type === "variable" ? "blue" : "purple"
                            }
                          >
                            {n.type === "variable" ? n.subtype : n.subtype}
                          </Tag>
                          <span style={{ flex: 1, fontSize: 12 }}>
                            {n.type === "variable"
                              ? n.label
                              : `[${n.subtype}]`}
                          </span>
                          <Tag
                            color={
                              edgeType === "background"
                                ? "cyan"
                                : isInput
                                  ? "green"
                                  : "orange"
                            }
                          >
                            {edgeType === "background"
                              ? "bg"
                              : isInput
                                ? "← in"
                                : "→ out"}
                          </Tag>
                        </List.Item>
                      );
                    }}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}

function renderGraph(
  data: GraphData,
  svg: SVGSVGElement,
  onNodeClick: (node: GraphNode) => void
) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: "TB",
    ranksep: 80,
    nodesep: 40,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));

  const nodeMap = new Map<string, GraphNode>();
  for (const node of data.nodes) {
    nodeMap.set(node.id, node);
    g.setNode(node.id, {
      width: node.type === "variable" ? 180 : 30,
      height: node.type === "variable" ? 50 : 30,
    });
  }

  // Build edge map for styling
  const edgeTypeMap = new Map<string, string>();
  for (const edge of data.edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      const key = `${edge.source}|${edge.target}`;
      edgeTypeMap.set(key, edge.type);
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  svg.innerHTML = "";

  // Defs: two arrow markers (solid + dashed)
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  for (const [id, color] of [
    ["arrow", "#999"],
    ["arrow-bg", "#52c41a"],
  ]) {
    const marker = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "marker"
    );
    marker.setAttribute("id", id);
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "10");
    marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("orient", "auto");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
    p.setAttribute("fill", color);
    marker.appendChild(p);
    defs.appendChild(marker);
  }
  svg.appendChild(defs);

  const contentGroup = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "g"
  );
  contentGroup.setAttribute("id", "graph-content");

  // Edges
  g.edges().forEach((e) => {
    const edge = g.edge(e);
    if (!edge?.points) return;
    const key = `${e.v}|${e.w}`;
    const edgeType = edgeTypeMap.get(key) ?? "premise";
    const isBg = edgeType === "background";

    const pathStr = edge.points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
      .join(" ");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute("d", pathStr);
    line.setAttribute("stroke", isBg ? "#52c41a" : "#999");
    line.setAttribute("stroke-width", isBg ? "1.5" : "1.5");
    line.setAttribute("fill", "none");
    line.setAttribute("marker-end", isBg ? "url(#arrow-bg)" : "url(#arrow)");
    if (isBg) {
      line.setAttribute("stroke-dasharray", "6,4");
      line.setAttribute("opacity", "0.7");
    }
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
      const w = layout.width,
        h = layout.height;

      const rect = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect"
      );
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

      group.addEventListener("mouseenter", () =>
        rect.setAttribute("stroke-width", "3")
      );
      group.addEventListener("mouseleave", () =>
        rect.setAttribute("stroke-width", "2")
      );

      const label = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text"
      );
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("y", node.prior != null ? "-4" : "4");
      label.setAttribute("font-size", "11");
      label.setAttribute("font-family", "system-ui, sans-serif");
      label.textContent =
        node.label.length > 22 ? node.label.slice(0, 20) + "…" : node.label;
      group.appendChild(label);

      if (node.prior != null) {
        const val = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text"
        );
        val.setAttribute("text-anchor", "middle");
        val.setAttribute("y", "14");
        val.setAttribute("font-size", "10");
        val.setAttribute("fill", "#888");
        val.textContent = `p = ${node.prior.toFixed(3)}`;
        group.appendChild(val);
      }
    } else {
      const r = 14;
      const circle = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );
      circle.setAttribute("r", String(r));
      const isCont = node.subtype === "contradiction";
      circle.setAttribute("fill", isCont ? "#fff0f0" : "#e8e8e8");
      circle.setAttribute("stroke", isCont ? "#ff4d4f" : "#999");
      circle.setAttribute("stroke-width", "2");
      group.appendChild(circle);

      group.addEventListener("mouseenter", () =>
        circle.setAttribute("stroke-width", "3")
      );
      group.addEventListener("mouseleave", () =>
        circle.setAttribute("stroke-width", "2")
      );

      const sym = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text"
      );
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
