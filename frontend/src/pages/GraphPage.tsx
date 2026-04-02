import { useEffect, useRef, useState } from "react";
import { Spin, Card, Statistic, Row, Col } from "antd";

interface GraphNode {
  id: string;
  type: "variable" | "factor";
  subtype: string;
  visibility?: string;
  content?: string | null;
  factor_type?: string;
  local_members_count?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: "premise" | "conclusion";
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  claim: "#1890ff",
  setting: "#52c41a",
  question: "#faad14",
  // factors
  strategy: "#722ed1",
  operator: "#13c2c2",
};

export default function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    fetch("/api/graph")
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!data || !svgRef.current) return;

    // Simple force-directed layout using basic physics
    const width = svgRef.current.clientWidth || 1200;
    const height = 800;
    const nodes = data.nodes.map((n, i) => ({
      ...n,
      x: width / 2 + (Math.random() - 0.5) * 600,
      y: height / 2 + (Math.random() - 0.5) * 400,
      vx: 0,
      vy: 0,
    }));
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // Run simple simulation
    for (let iter = 0; iter < 200; iter++) {
      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 5000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          nodes[i].vx -= fx;
          nodes[i].vy -= fy;
          nodes[j].vx += fx;
          nodes[j].vy += fy;
        }
      }

      // Attraction along edges
      for (const edge of data.edges) {
        const s = nodeMap.get(edge.source);
        const t = nodeMap.get(edge.target);
        if (!s || !t) continue;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = dist * 0.01;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        s.vx += fx;
        s.vy += fy;
        t.vx -= fx;
        t.vy -= fy;
      }

      // Apply velocities with damping
      for (const n of nodes) {
        n.x += n.vx * 0.1;
        n.y += n.vy * 0.1;
        n.vx *= 0.9;
        n.vy *= 0.9;
        // Keep in bounds
        n.x = Math.max(50, Math.min(width - 50, n.x));
        n.y = Math.max(50, Math.min(height - 50, n.y));
      }
    }

    // Render SVG
    const svg = svgRef.current;
    svg.innerHTML = "";
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    // Edges
    for (const edge of data.edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t) continue;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(s.x));
      line.setAttribute("y1", String(s.y));
      line.setAttribute("x2", String(t.x));
      line.setAttribute("y2", String(t.y));
      line.setAttribute("stroke", edge.type === "premise" ? "#999" : "#666");
      line.setAttribute("stroke-width", "0.5");
      line.setAttribute("opacity", "0.4");
      svg.appendChild(line);
    }

    // Nodes
    for (const n of nodes) {
      const colorKey =
        n.type === "variable" ? n.subtype : n.factor_type || "strategy";
      const color = NODE_COLORS[colorKey] || "#999";
      const r = n.type === "variable" ? 4 : 3;

      const circle = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle"
      );
      circle.setAttribute("cx", String(n.x));
      circle.setAttribute("cy", String(n.y));
      circle.setAttribute("r", String(r));
      circle.setAttribute("fill", color);
      circle.setAttribute("opacity", "0.8");

      // Tooltip
      const title = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "title"
      );
      const label =
        n.type === "variable"
          ? `[${n.subtype}] ${(n.content || "").slice(0, 60)}`
          : `[${n.factor_type}/${n.subtype}]`;
      title.textContent = `${n.id}\n${label}`;
      circle.appendChild(title);
      svg.appendChild(circle);
    }
  }, [data]);

  if (loading) return <Spin size="large" />;
  if (!data) return <div>Failed to load graph</div>;

  const varNodes = data.nodes.filter((n) => n.type === "variable");
  const facNodes = data.nodes.filter((n) => n.type === "factor");

  return (
    <>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card>
            <Statistic title="Variables" value={varNodes.length} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="Factors" value={facNodes.length} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="Edges" value={data.edges.length} />
          </Card>
        </Col>
        <Col span={12}>
          <Card>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {Object.entries(NODE_COLORS).map(([k, c]) => (
                <span key={k}>
                  <span
                    style={{
                      display: "inline-block",
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      backgroundColor: c,
                      marginRight: 4,
                    }}
                  />
                  {k}
                </span>
              ))}
            </div>
          </Card>
        </Col>
      </Row>
      <Card>
        <svg
          ref={svgRef}
          width="100%"
          height="800"
          style={{ border: "1px solid #f0f0f0" }}
        />
      </Card>
    </>
  );
}
