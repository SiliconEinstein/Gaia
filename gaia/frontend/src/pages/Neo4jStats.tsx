import { useState, useEffect } from 'react';
import { Card, Spin, Alert, Row, Col, Statistic } from 'antd';
import {
  NodeIndexOutlined,
  ApartmentOutlined,
  BranchesOutlined,
} from '@ant-design/icons';
import { getNeo4jStats } from '../api/client';

export default function Neo4jStats() {
  const [stats, setStats] = useState<{
    knowledge_nodes: number;
    factor_nodes: number;
    edges: number;
    available: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNeo4jStats()
      .then((data) => setStats(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 64 }} />;
  if (error) return <Alert type="error" message={error} showIcon />;
  if (!stats) return null;

  return (
    <Row gutter={[24, 24]}>
      <Col xs={24} sm={8}>
        <Card>
          <Statistic
            title="Knowledge Nodes"
            value={stats.knowledge_nodes}
            prefix={<NodeIndexOutlined />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={8}>
        <Card>
          <Statistic
            title="Factor Nodes"
            value={stats.factor_nodes}
            prefix={<ApartmentOutlined />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={8}>
        <Card>
          <Statistic
            title="Edges"
            value={stats.edges}
            prefix={<BranchesOutlined />}
          />
        </Card>
      </Col>
    </Row>
  );
}
