// frontend/src/pages/v2/KnowledgeList.tsx
import { useState } from "react";
import { Table, Select, Tag, Typography, Space } from "antd";
import { Link } from "react-router-dom";
import { useKnowledgeList } from "../../api/v2";
import type { V2Knowledge, KnowledgeType } from "../../api/v2-types";

const TYPE_COLORS: Record<KnowledgeType, string> = {
  claim: "blue",
  setting: "green",
  question: "orange",
  action: "purple",
};

const KNOWLEDGE_TYPES: KnowledgeType[] = ["claim", "question", "setting", "action"];

const columns = [
  {
    title: "Knowledge ID",
    dataIndex: "knowledge_id",
    ellipsis: true,
    render: (id: string) => (
      <Link to={`/v2/knowledge/${encodeURIComponent(id)}`}>{id}</Link>
    ),
  },
  {
    title: "Type",
    dataIndex: "type",
    width: 100,
    render: (t: KnowledgeType) => <Tag color={TYPE_COLORS[t]}>{t}</Tag>,
  },
  { title: "v", dataIndex: "version", width: 50 },
  { title: "Prior", dataIndex: "prior", width: 70, render: (p: number) => p.toFixed(2) },
  { title: "Content", dataIndex: "content", ellipsis: true },
];

export function KnowledgeList() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<KnowledgeType | undefined>();
  const PAGE_SIZE = 20;
  const { data, isLoading, error } = useKnowledgeList(page, PAGE_SIZE, typeFilter);

  if (error) return <Typography.Text type="danger">Failed to load knowledge</Typography.Text>;

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Knowledge
      </Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Filter by type"
          style={{ width: 160 }}
          options={KNOWLEDGE_TYPES.map((t) => ({ value: t, label: t }))}
          onChange={(v) => {
            setTypeFilter(v);
            setPage(1);
          }}
        />
      </Space>
      <Table<V2Knowledge>
        rowKey={(r) => `${r.knowledge_id}@${r.version}`}
        columns={columns}
        dataSource={data?.items ?? []}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: data?.total ?? 0,
          onChange: setPage,
          showTotal: (t) => `${t} items`,
        }}
      />
    </div>
  );
}
