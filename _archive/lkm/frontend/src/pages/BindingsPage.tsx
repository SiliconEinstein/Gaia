import { useEffect, useState } from "react";
import { Table, Tag, Select, Space, Spin } from "antd";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Binding } from "../api";

export default function BindingsPage() {
  const [data, setData] = useState<Binding[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>();

  useEffect(() => {
    setLoading(true);
    api
      .bindings({ binding_type: typeFilter })
      .then(setData)
      .finally(() => setLoading(false));
  }, [typeFilter]);

  const columns = [
    {
      title: "Local ID",
      dataIndex: "local_id",
      key: "local_id",
      ellipsis: true,
      render: (id: string) => <code>{id}</code>,
    },
    {
      title: "Global ID",
      dataIndex: "global_id",
      key: "global_id",
      width: 220,
      render: (id: string) => (
        <Link to={`/variables/${encodeURIComponent(id)}`}>
          <code>{id}</code>
        </Link>
      ),
    },
    {
      title: "Type",
      dataIndex: "binding_type",
      key: "binding_type",
      width: 100,
      render: (t: string) => <Tag>{t}</Tag>,
    },
    {
      title: "Decision",
      dataIndex: "decision",
      key: "decision",
      width: 140,
      render: (d: string) => (
        <Tag color={d === "match_existing" ? "green" : "blue"}>{d}</Tag>
      ),
    },
    {
      title: "Package",
      dataIndex: "package_id",
      key: "package_id",
      width: 180,
    },
    {
      title: "Reason",
      dataIndex: "reason",
      key: "reason",
      ellipsis: true,
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <span>Binding Type:</span>
        <Select
          allowClear
          placeholder="All"
          style={{ width: 150 }}
          value={typeFilter}
          onChange={setTypeFilter}
          options={[
            { value: "variable", label: "Variable" },
            { value: "factor", label: "Factor" },
          ]}
        />
      </Space>
      {loading ? (
        <Spin />
      ) : (
        <Table
          dataSource={data}
          columns={columns}
          rowKey={(r) => `${r.local_id}:${r.global_id}`}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      )}
    </>
  );
}
