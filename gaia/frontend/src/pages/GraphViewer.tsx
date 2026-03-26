import { useState, useEffect } from 'react';
import { Radio, Select, Spin, Alert, Space, Typography } from 'antd';
import { getGraph } from '../api/client';
import GraphCanvas from '../components/GraphCanvas';

const { Title } = Typography;

interface GraphNode {
  id: string;
  label: string;
  type: string;
  reasoning_type?: string;
  belief?: number;
  prior?: number;
}

interface GraphEdge {
  from: string;
  to: string;
  role: string;
}

export default function GraphViewer() {
  const [scope, setScope] = useState<'global' | 'local'>('global');
  const [packageId, setPackageId] = useState<string | undefined>(undefined);
  const [packages, setPackages] = useState<string[]>([]);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load graph data
  useEffect(() => {
    if (scope === 'local' && !packageId) return;
    setLoading(true);
    setError(null);
    getGraph(scope, packageId)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
        if (data.packages) setPackages(data.packages);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [scope, packageId]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          Graph Viewer
        </Title>
        <Space>
          <Radio.Group value={scope} onChange={(e) => setScope(e.target.value)}>
            <Radio.Button value="global">Global</Radio.Button>
            <Radio.Button value="local">Per-package</Radio.Button>
          </Radio.Group>
          {scope === 'local' && (
            <Select
              placeholder="Select package"
              style={{ width: 240 }}
              value={packageId}
              onChange={(val) => setPackageId(val)}
              options={packages.map((p) => ({ value: p, label: p }))}
              showSearch
            />
          )}
        </Space>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      {loading ? (
        <Spin size="large" style={{ display: 'block', marginTop: 64 }} />
      ) : nodes.length === 0 ? (
        <Alert type="info" message="No graph data available. Try ingesting a package first." showIcon />
      ) : (
        <>
          <div style={{ marginBottom: 8, color: '#888', fontSize: 13 }}>
            {nodes.length} nodes, {edges.length} edges
          </div>
          <GraphCanvas nodes={nodes} edges={edges} />
        </>
      )}
    </div>
  );
}
