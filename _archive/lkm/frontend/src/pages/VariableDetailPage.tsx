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
  Table,
} from "antd";
import { api } from "../api";
import type { VariableDetail } from "../api";

const { Text, Paragraph } = Typography;

export default function VariableDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<VariableDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api
      .variable(id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spin size="large" />;
  if (!data) return <div>Variable not found</div>;

  return (
    <>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/variables">Variables</Link> },
          { title: <code>{data.id}</code> },
        ]}
      />

      <Card title="Variable" style={{ marginBottom: 16 }}>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="ID">
            <code>{data.id}</code>
          </Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag>{data.type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Visibility">
            {data.visibility}
          </Descriptions.Item>
          <Descriptions.Item label="Content Hash">
            <code>{data.content_hash.slice(0, 16)}...</code>
          </Descriptions.Item>
          <Descriptions.Item label="Content" span={2}>
            <Paragraph>{data.content}</Paragraph>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title={`Local Members (${data.local_members.length})`}
        style={{ marginBottom: 16 }}
      >
        <List
          size="small"
          dataSource={data.local_members}
          renderItem={(m) => (
            <List.Item>
              <code>{m.local_id}</code>
              <Text type="secondary" style={{ marginLeft: 8 }}>
                {m.package_id}@{m.version}
              </Text>
            </List.Item>
          )}
        />
      </Card>

      {data.connected_factors.length > 0 && (
        <Card
          title={`Connected Factors (${data.connected_factors.length})`}
          style={{ marginBottom: 16 }}
        >
          <Table
            dataSource={data.connected_factors}
            rowKey="id"
            size="small"
            pagination={false}
            columns={[
              {
                title: "ID",
                dataIndex: "id",
                render: (id: string) => (
                  <Link to={`/factors/${encodeURIComponent(id)}`}>
                    <code>{id.slice(0, 20)}...</code>
                  </Link>
                ),
              },
              {
                title: "Type",
                dataIndex: "subtype",
                render: (s: string) => <Tag>{s}</Tag>,
              },
              { title: "Role", dataIndex: "role" },
              {
                title: "Reasoning",
                dataIndex: "steps",
                render: (steps: { reasoning: string }[] | null) =>
                  steps?.[0]?.reasoning || "-",
                ellipsis: true,
              },
            ]}
          />
        </Card>
      )}

      {data.bindings.length > 0 && (
        <Card title={`Bindings (${data.bindings.length})`}>
          <Table
            dataSource={data.bindings}
            rowKey="local_id"
            size="small"
            pagination={false}
            columns={[
              {
                title: "Local ID",
                dataIndex: "local_id",
                ellipsis: true,
                render: (id: string) => <code>{id}</code>,
              },
              {
                title: "Decision",
                dataIndex: "decision",
                render: (d: string) => (
                  <Tag color={d === "match_existing" ? "green" : "blue"}>
                    {d}
                  </Tag>
                ),
              },
              { title: "Package", dataIndex: "package_id" },
              { title: "Reason", dataIndex: "reason", ellipsis: true },
            ]}
          />
        </Card>
      )}
    </>
  );
}
