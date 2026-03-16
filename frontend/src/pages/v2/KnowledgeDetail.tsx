// frontend/src/pages/v2/KnowledgeDetail.tsx
import { Breadcrumb, Card, Descriptions, Table, Tag, Tabs, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useKnowledge, useKnowledgeVersions, useKnowledgeBeliefs } from "../../api/v2";
import type { V2Knowledge, V2BeliefSnapshot } from "../../api/v2-types";

const TYPE_COLORS: Record<string, string> = {
  claim: "blue", setting: "green", question: "orange", action: "purple",
};

export function KnowledgeDetail() {
  const { id } = useParams<{ id: string }>();
  const knowledgeId = decodeURIComponent(id ?? "");
  const { data: k, isLoading } = useKnowledge(knowledgeId);
  const { data: versions } = useKnowledgeVersions(knowledgeId);
  const { data: beliefs } = useKnowledgeBeliefs(knowledgeId);

  if (isLoading) return <Spin />;
  if (!k) return <Typography.Text type="danger">Knowledge not found</Typography.Text>;

  const beliefColumns = [
    { title: "Belief", dataIndex: "belief", render: (v: number) => v.toFixed(4) },
    { title: "BP Run", dataIndex: "bp_run_id" },
    { title: "Computed At", dataIndex: "computed_at" },
  ];

  const versionColumns = [
    { title: "Version", dataIndex: "version" },
    { title: "Type", dataIndex: "type", render: (t: string) => <Tag color={TYPE_COLORS[t]}>{t}</Tag> },
    { title: "Prior", dataIndex: "prior", render: (p: number) => p.toFixed(2) },
    { title: "Content", dataIndex: "content", ellipsis: true },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/knowledge">Knowledge</Link> },
          { title: k.knowledge_id },
        ]}
      />
      <Typography.Title level={3}>
        <Tag color={TYPE_COLORS[k.type]}>{k.type}</Tag> {k.knowledge_id}
      </Typography.Title>
      <Tabs
        items={[
          {
            key: "content",
            label: "Content",
            children: (
              <Card>
                <Descriptions bordered column={2}>
                  <Descriptions.Item label="Prior">{k.prior.toFixed(2)}</Descriptions.Item>
                  <Descriptions.Item label="Version">{k.version}</Descriptions.Item>
                  <Descriptions.Item label="Package">
                    <Link to={`/v2/packages/${encodeURIComponent(k.source_package_id)}`}>
                      {k.source_package_id}
                    </Link>
                  </Descriptions.Item>
                  <Descriptions.Item label="Module">
                    <Link to={`/v2/modules/${encodeURIComponent(k.source_module_id)}`}>
                      {k.source_module_id}
                    </Link>
                  </Descriptions.Item>
                  <Descriptions.Item label="Keywords" span={2}>
                    {k.keywords.map((kw) => <Tag key={kw}>{kw}</Tag>)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Content" span={2}>
                    <Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{k.content}</Typography.Paragraph>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: "versions",
            label: `Versions (${versions?.length ?? 0})`,
            children: (
              <Table<V2Knowledge>
                rowKey={(r) => String(r.version)}
                columns={versionColumns}
                dataSource={versions ?? []}
                pagination={false}
              />
            ),
          },
          {
            key: "beliefs",
            label: `Beliefs (${beliefs?.length ?? 0})`,
            children: (
              <Table<V2BeliefSnapshot>
                rowKey="bp_run_id"
                columns={beliefColumns}
                dataSource={beliefs ?? []}
                pagination={false}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
