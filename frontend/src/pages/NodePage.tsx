import { useParams, Link } from "react-router-dom";
import { Card, Descriptions, Tag, Spin, Alert, Button, Divider } from "antd";
import { DeploymentUnitOutlined } from "@ant-design/icons";
import { useNode } from "../hooks/useNode";
import { ContentRenderer } from "../components/shared/ContentRenderer";

export function NodePage() {
  const { id } = useParams<{ id: string }>();
  const nodeId = id ? Number(id) : null;
  const { data: node, isLoading, error } = useNode(nodeId);

  if (isLoading) return <Spin size="large" />;
  if (error) return <Alert type="error" message={String(error)} />;
  if (!node) return <Alert type="warning" message="Node not found" />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Node {node.id}</h2>
        <Link to={`/graph?node=${node.id}&hops=1`}>
          <Button icon={<DeploymentUnitOutlined />}>View in Graph</Button>
        </Link>
      </div>

      <Card>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="ID">{node.id}</Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag>{node.type}</Tag>
          </Descriptions.Item>
          {node.subtype && (
            <Descriptions.Item label="Subtype">{node.subtype}</Descriptions.Item>
          )}
          {node.title && (
            <Descriptions.Item label="Title" span={2}>
              {node.title}
            </Descriptions.Item>
          )}
          <Descriptions.Item label="Prior">{node.prior}</Descriptions.Item>
          <Descriptions.Item label="Belief">
            {node.belief !== null ? node.belief : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={node.status === "active" ? "green" : "red"}>
              {node.status}
            </Tag>
          </Descriptions.Item>
          {node.keywords.length > 0 && (
            <Descriptions.Item label="Keywords" span={2}>
              {node.keywords.map((kw) => (
                <Tag key={kw}>{kw}</Tag>
              ))}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Divider orientation="left">Content</Divider>
      <Card>
        <ContentRenderer content={node.content} />
      </Card>
    </div>
  );
}
