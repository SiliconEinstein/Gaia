import { useEffect, useRef, useState } from "react";
import { Spin, Card, Select, Space, Row, Col, Statistic } from "antd";
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

// Colors by variable type
const VAR_STYLES: Record<
  string,
  { fill: string; stroke: string; dash?: boolean }
> = {
  claim: { fill: "#f0f0f0", stroke: "#666" },
  setting: { fill: "#e6f7e6", stroke: "#52c41a" },
  question: { fill: "#fff7e6", stroke: "#faad14", dash: true },
};

// Factor symbols
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
  const svgRef = useRef<SVGSVGElement>(null);

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
    renderGraph(data, svgRef.current);
  }, [data]);

  const varNodes = data?.nodes.filter((n) => n.type === "variable") ?? [];
  const facNodes = data?.nodes.filter((n) => n.type === "factor") ?? [];

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
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12 }}>
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
        <Card style={{ overflow: "auto" }}>
          <svg ref={svgRef} style={{ minHeight: 600 }} />
        </Card>
      )}
    </>
  );
}

function renderGraph(data: GraphData, svg: SVGSVGElement) {
  // Build dagre graph
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

  // Calculate SVG dimensions
  let maxX = 0, maxY = 0;
  g.nodes().forEach((id) => {
    const n = g.node(id);
    if (n) {
      maxX = Math.max(maxX, n.x + n.width / 2);
      maxY = Math.max(maxY, n.y + n.height / 2);
    }
  });

  svg.setAttribute("width", String(maxX + 60));
  svg.setAttribute("height", String(maxY + 60));
  svg.innerHTML = "";

  // Defs for arrowheads
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
  marker.setAttribute("id", "arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "10");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "8");
  marker.setAttribute("markerHeight", "8");
  marker.setAttribute("orient", "auto");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  path.setAttribute("fill", "#999");
  marker.appendChild(path);
  defs.appendChild(marker);
  svg.appendChild(defs);

  // Draw edges
  g.edges().forEach((e) => {
    const edge = g.edge(e);
    if (!edge || !edge.points) return;
    const points = edge.points;
    const pathStr = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute("d", pathStr);
    line.setAttribute("stroke", "#999");
    line.setAttribute("stroke-width", "1.5");
    line.setAttribute("fill", "none");
    line.setAttribute("marker-end", "url(#arrow)");
    svg.appendChild(line);
  });

  // Draw nodes
  g.nodes().forEach((id) => {
    const layout = g.node(id);
    const node = nodeMap.get(id);
    if (!layout || !node) return;

    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("transform", `translate(${layout.x}, ${layout.y})`);

    if (node.type === "variable") {
      const style = VAR_STYLES[node.subtype] || VAR_STYLES.claim;
      const w = layout.width;
      const h = layout.height;

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

      // Label (short name)
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("y", node.prior != null ? "-4" : "4");
      label.setAttribute("font-size", "11");
      label.setAttribute("font-family", "system-ui, sans-serif");
      label.textContent = node.label.length > 22 ? node.label.slice(0, 20) + "…" : node.label;
      group.appendChild(label);

      // Prior/belief value
      if (node.prior != null) {
        const val = document.createElementNS("http://www.w3.org/2000/svg", "text");
        val.setAttribute("text-anchor", "middle");
        val.setAttribute("y", "14");
        val.setAttribute("font-size", "10");
        val.setAttribute("fill", "#888");
        val.textContent = `p = ${node.prior.toFixed(3)}`;
        group.appendChild(val);
      }

      // Tooltip
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${node.id}\n[${node.subtype}] ${node.content || ""}`;
      group.appendChild(title);
    } else {
      // Factor node — small circle with symbol
      const r = 14;
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", String(r));

      const isContradiction = node.subtype === "contradiction";
      circle.setAttribute("fill", isContradiction ? "#fff0f0" : "#e8e8e8");
      circle.setAttribute("stroke", isContradiction ? "#ff4d4f" : "#999");
      circle.setAttribute("stroke-width", "2");
      group.appendChild(circle);

      const sym = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sym.setAttribute("text-anchor", "middle");
      sym.setAttribute("y", "5");
      sym.setAttribute("font-size", "14");
      sym.setAttribute("font-weight", "bold");
      sym.setAttribute("fill", isContradiction ? "#ff4d4f" : "#666");
      sym.textContent = FACTOR_SYMBOLS[node.subtype] || "f";
      group.appendChild(sym);

      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${node.id}\n[${node.factor_type}/${node.subtype}]`;
      group.appendChild(title);
    }

    svg.appendChild(group);
  });
}
