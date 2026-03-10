import { useParams, Link } from "react-router-dom";
import { Card, Descriptions, Tag, Spin, Alert, Divider } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchEdge } from "../api/edges";
import { ReasoningSteps } from "../components/shared/ReasoningSteps";

export function EdgePage() {
  const { id } = useParams<{ id: string }>();
  const edgeId = id ? Number(id) : null;

  const {
    data: edge,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["edge", edgeId],
    queryFn: () => fetchEdge(edgeId!),
    enabled: edgeId !== null,
  });

  if (isLoading) return <Spin size="large" />;
  if (error) return <Alert type="error" message={String(error)} />;
  if (!edge) return <Alert type="warning" message="Edge not found" />;

  return (
    <div>
      <h2>HyperEdge {edge.id}</h2>

      <Card>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="ID">{edge.id}</Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag>{edge.type}</Tag>
          </Descriptions.Item>
          {edge.subtype && (
            <Descriptions.Item label="Subtype">{edge.subtype}</Descriptions.Item>
          )}
          <Descriptions.Item label="Premises">
            {edge.premises.map((id) => (
              <Link key={id} to={`/nodes/${id}`}>
                <Tag color="blue">Node {id}</Tag>
              </Link>
            ))}
          </Descriptions.Item>
          <Descriptions.Item label="Conclusions">
            {edge.conclusions.map((id) => (
              <Link key={id} to={`/nodes/${id}`}>
                <Tag color="green">Node {id}</Tag>
              </Link>
            ))}
          </Descriptions.Item>
          <Descriptions.Item label="Probability">
            {edge.probability !== null ? edge.probability : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="Verified">
            <Tag color={edge.verified ? "green" : "default"}>
              {edge.verified ? "Yes" : "No"}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Divider orientation="left">Reasoning Steps</Divider>
      <Card>
        <ReasoningSteps steps={edge.reasoning} />
      </Card>

      <div style={{ marginTop: 16 }}>
        <Link to={`/graph?node=${edge.premises[0] ?? edge.conclusions[0]}&hops=1`}>
          View in Graph
        </Link>
      </div>
    </div>
  );
}
