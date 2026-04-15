import { useEffect, useState } from "react";
import { Table, Tag, Select, Space, Spin, Tabs } from "antd";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Factor } from "../api";

interface LocalFactor {
  id: string;
  factor_type: string;
  subtype: string;
  premises: string[];
  conclusion: string;
  background: string[] | null;
  steps: { reasoning: string }[] | null;
  source_package: string;
  version: string;
}

export default function FactorsPage() {
  const [layer, setLayer] = useState<string>("global");
  const [globalData, setGlobalData] = useState<Factor[]>([]);
  const [localData, setLocalData] = useState<LocalFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>();

  useEffect(() => {
    setLoading(true);
    if (layer === "global") {
      api
        .factors({ factor_type: typeFilter, limit: 200 })
        .then(setGlobalData)
        .finally(() => setLoading(false));
    } else {
      fetch(
        `/api/factors?layer=local&limit=200${typeFilter ? `&factor_type=${typeFilter}` : ""}`
      )
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
        <Link to={`/factors/${encodeURIComponent(id)}`}>
          <code>{id}</code>
        </Link>
      ),
    },
    {
      title: "Type",
      dataIndex: "factor_type",
      key: "factor_type",
      width: 100,
      render: (t: string) => (
        <Tag color={t === "strategy" ? "purple" : "cyan"}>{t}</Tag>
      ),
    },
    {
      title: "Subtype",
      dataIndex: "subtype",
      key: "subtype",
      width: 120,
      render: (s: string) => <Tag>{s}</Tag>,
    },
    {
      title: "Premises",
      dataIndex: "premises",
      key: "premises",
      width: 80,
      render: (p: string[]) => p.length,
    },
    {
      title: "Package",
      dataIndex: "source_package",
      key: "source_package",
      width: 180,
    },
    {
      title: "Reasoning",
      key: "reasoning",
      ellipsis: true,
      render: (_: unknown, record: Factor) =>
        record.steps?.[0]?.reasoning || "-",
    },
  ];

  const localColumns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 200,
      ellipsis: true,
      render: (id: string) => <code>{id}</code>,
    },
    {
      title: "Type",
      dataIndex: "factor_type",
      key: "factor_type",
      width: 100,
      render: (t: string) => (
        <Tag color={t === "strategy" ? "purple" : "cyan"}>{t}</Tag>
      ),
    },
    {
      title: "Subtype",
      dataIndex: "subtype",
      key: "subtype",
      width: 120,
      render: (s: string) => <Tag>{s}</Tag>,
    },
    {
      title: "Premises",
      dataIndex: "premises",
      key: "premises",
      ellipsis: true,
      render: (p: string[]) => p.map((id) => id.split("::")[1] || id).join(", "),
    },
    {
      title: "Conclusion",
      dataIndex: "conclusion",
      key: "conclusion",
      width: 180,
      ellipsis: true,
      render: (c: string) => c.split("::")[1] || c,
    },
    {
      title: "Package",
      dataIndex: "source_package",
      key: "source_package",
      width: 160,
    },
    {
      title: "Reasoning",
      key: "reasoning",
      ellipsis: true,
      render: (_: unknown, record: LocalFactor) =>
        record.steps?.[0]?.reasoning || "-",
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
          placeholder="All"
          style={{ width: 150 }}
          value={typeFilter}
          onChange={setTypeFilter}
          options={[
            { value: "strategy", label: "Strategy" },
            { value: "operator", label: "Operator" },
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
