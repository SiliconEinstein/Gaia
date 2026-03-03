import { useQuery } from "@tanstack/react-query";
import { Card, Row, Col, Statistic, Tag, Alert, Spin } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
} from "@ant-design/icons";
import { fetchHealth, fetchStats } from "../api/commits";

export function DashboardHome() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
  const stats = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  return (
    <div>
      <h2>Gaia Knowledge Graph Dashboard</h2>

      {health.error && (
        <Alert
          type="error"
          message="Backend Unreachable"
          description="Cannot connect to Gaia API. Make sure the server is running on port 8000."
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="API Status"
              value={health.data?.status ?? "—"}
              prefix={
                health.data?.status === "ok" ? (
                  <CheckCircleOutlined style={{ color: "#52c41a" }} />
                ) : (
                  <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
                )
              }
            />
            {health.data?.version && (
              <Tag style={{ marginTop: 8 }}>v{health.data.version}</Tag>
            )}
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            {stats.isLoading ? (
              <Spin />
            ) : (
              <Statistic
                title="Nodes"
                value={stats.data?.node_count ?? 0}
                prefix={<NodeIndexOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            {stats.isLoading ? (
              <Spin />
            ) : (
              <Statistic
                title="Edges"
                value={stats.data?.edge_count ?? 0}
                prefix={<BranchesOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Graph Store"
              value={stats.data?.graph_available ? "Connected" : "Unavailable"}
              valueStyle={{
                color: stats.data?.graph_available ? "#52c41a" : "#faad14",
              }}
            />
          </Card>
        </Col>
      </Row>

      {stats.data?.node_types &&
        Object.keys(stats.data.node_types).length > 0 && (
          <Card title="Nodes by Type" style={{ marginTop: 16 }}>
            <Row gutter={16}>
              {Object.entries(stats.data.node_types).map(([type, count]) => (
                <Col span={6} key={type}>
                  <Statistic title={type} value={count} />
                </Col>
              ))}
            </Row>
          </Card>
        )}
    </div>
  );
}
