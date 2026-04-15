import { useEffect, useState } from "react";
import { Table, Tag, Select, Space, Spin, Tabs } from "antd";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Variable } from "../api";

const typeColors: Record<string, string> = {
  claim: "blue",
  setting: "green",
  question: "orange",
};

interface LocalVar {
  id: string;
  type: string;
  visibility: string;
  content: string;
  content_hash: string;
  source_package: string;
  version: string;
  parameters: { name: string; type: string }[];
}

export default function VariablesPage() {
  const [layer, setLayer] = useState<string>("global");
  const [globalData, setGlobalData] = useState<Variable[]>([]);
  const [localData, setLocalData] = useState<LocalVar[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>();

  useEffect(() => {
    setLoading(true);
    if (layer === "global") {
      api
        .variables({ type: typeFilter, limit: 200 })
        .then(setGlobalData)
        .finally(() => setLoading(false));
    } else {
      fetch(`/api/variables?layer=local&limit=200${typeFilter ? `&type=${typeFilter}` : ""}`)
        .then((r) => r.json())
        .then(setLocalData)
        .finally(() => setLoading(false));
    }
  }, [layer, typeFilter]);

  const globalColumns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 200,
      ellipsis: true,
      render: (id: string) => (
        <Link to={`/variables/${encodeURIComponent(id)}`}>
          <code>{id}</code>
        </Link>
      ),
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 100,
      render: (t: string) => <Tag color={typeColors[t]}>{t}</Tag>,
    },
    {
      title: "Content",
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: "Sources",
      dataIndex: "local_members",
      key: "sources",
      width: 80,
      render: (_: unknown, record: Variable) =>
        record.local_members?.length ?? record.local_members_count ?? 0,
    },
    {
      title: "Hash",
      dataIndex: "content_hash",
      key: "hash",
      width: 120,
      ellipsis: true,
      render: (h: string) => <code>{h.slice(0, 12)}...</code>,
    },
  ];

  const localColumns = [
    {
      title: "QID",
      dataIndex: "id",
      key: "id",
      width: 300,
      ellipsis: true,
      render: (id: string) => <code>{id}</code>,
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 100,
      render: (t: string) => <Tag color={typeColors[t]}>{t}</Tag>,
    },
    {
      title: "Content",
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: "Package",
      dataIndex: "source_package",
      key: "source_package",
      width: 180,
    },
    {
      title: "Version",
      dataIndex: "version",
      key: "version",
      width: 80,
    },
    {
      title: "Hash",
      dataIndex: "content_hash",
      key: "hash",
      width: 120,
      ellipsis: true,
      render: (h: string) => <code>{h.slice(0, 12)}...</code>,
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Tabs
          activeKey={layer}
          onChange={setLayer}
          items={[
            { key: "global", label: `Global (${layer === "global" ? globalData.length : "..."})` },
            { key: "local", label: `Local (${layer === "local" ? localData.length : "..."})` },
          ]}
          style={{ marginBottom: 0 }}
        />
        <Select
          allowClear
          placeholder="All types"
          style={{ width: 150 }}
          value={typeFilter}
          onChange={setTypeFilter}
          options={[
            { value: "claim", label: "Claim" },
            { value: "setting", label: "Setting" },
            { value: "question", label: "Question" },
          ]}
        />
      </Space>
      {loading ? (
        <Spin />
      ) : layer === "global" ? (
        <Table
          dataSource={globalData}
          columns={globalColumns}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          size="small"
        />
      ) : (
        <Table
          dataSource={localData}
          columns={localColumns}
          rowKey="id"
          pagination={{ pageSize: 20 }}
          size="small"
        />
      )}
    </>
  );
}
