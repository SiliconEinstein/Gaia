import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Descriptions,
  Tag,
  Card,
  List,
  Spin,
  Breadcrumb,
  Typography,
} from "antd";
import { api } from "../api";
import type { FactorDetail } from "../api";

const { Paragraph } = Typography;

export default function FactorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<FactorDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api
      .factor(id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spin size="large" />;
  if (!data) return <div>Factor not found</div>;

  return (
    <>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/factors">Factors</Link> },
          { title: <code>{data.id}</code> },
        ]}
      />

      <Card title="Factor" style={{ marginBottom: 16 }}>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="ID">
            <code>{data.id}</code>
          </Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag color={data.factor_type === "strategy" ? "purple" : "cyan"}>
              {data.factor_type}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Subtype">
            <Tag>{data.subtype}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Package">
            {data.source_package}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Premises" style={{ marginBottom: 16 }}>
        <List
          size="small"
          dataSource={data.premises}
          renderItem={(p) => (
            <List.Item>
              <Link to={`/variables/${encodeURIComponent(p.id)}`}>
                <code>{p.id}</code>
              </Link>
              {p.content && (
                <Paragraph
                  style={{ margin: "0 0 0 12px", flex: 1 }}
                  ellipsis={{ rows: 1 }}
                >
                  {p.content}
                </Paragraph>
              )}
            </List.Item>
          )}
        />
      </Card>

      <Card title="Conclusion" style={{ marginBottom: 16 }}>
        <Link to={`/variables/${encodeURIComponent(data.conclusion.id)}`}>
          <code>{data.conclusion.id}</code>
        </Link>
        {data.conclusion.content && (
          <Paragraph style={{ marginTop: 8 }}>
            {data.conclusion.content}
          </Paragraph>
        )}
      </Card>

      {data.steps && data.steps.length > 0 && (
        <Card title="Reasoning Steps">
          <List
            size="small"
            dataSource={data.steps}
            renderItem={(step, i) => (
              <List.Item>
                <strong>Step {i + 1}:</strong> {step.reasoning}
              </List.Item>
            )}
          />
        </Card>
      )}
    </>
  );
}
