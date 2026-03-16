// frontend/src/pages/v2/PackageList.tsx
import { useState } from "react";
import { Table, Tag, Typography, Input } from "antd";
import { Link } from "react-router-dom";
import { usePackages } from "../../api/v2";
import type { V2Package } from "../../api/v2-types";

const STATUS_COLORS: Record<string, string> = {
  merged: "green",
  submitted: "blue",
  preparing: "orange",
  rejected: "red",
};

const columns = [
  {
    title: "Package ID",
    dataIndex: "package_id",
    render: (id: string) => <Link to={`/v2/packages/${encodeURIComponent(id)}`}>{id}</Link>,
  },
  { title: "Version", dataIndex: "version", width: 100 },
  {
    title: "Status",
    dataIndex: "status",
    width: 110,
    render: (s: string) => <Tag color={STATUS_COLORS[s] ?? "default"}>{s}</Tag>,
  },
  { title: "Submitter", dataIndex: "submitter", width: 160 },
  { title: "Description", dataIndex: "description", ellipsis: true },
];

export function PackageList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const PAGE_SIZE = 20;
  const { data, isLoading, error } = usePackages(page, PAGE_SIZE);

  if (error) return <Typography.Text type="danger">Failed to load packages</Typography.Text>;

  const filtered = search
    ? (data?.items ?? []).filter(
        (p) => p.package_id.includes(search) || p.description.includes(search),
      )
    : (data?.items ?? []);

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Packages
      </Typography.Title>
      <Input.Search
        placeholder="Search by package ID or description"
        style={{ width: 360, marginBottom: 16 }}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
        allowClear
      />
      <Table<V2Package>
        rowKey="package_id"
        columns={columns}
        dataSource={filtered}
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: data?.total ?? 0,
          onChange: setPage,
          showTotal: (t) => `${t} packages`,
        }}
      />
    </div>
  );
}
