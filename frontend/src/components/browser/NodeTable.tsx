import { useState } from "react";
import { Table, Tag } from "antd";
import { Link } from "react-router-dom";
import { useNodes } from "../../hooks/useNode";
import { FilterBar } from "./FilterBar";
import type { Node } from "../../api/types";

export function NodeTable() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [typeFilter, setTypeFilter] = useState("");

  const { data, isLoading } = useNodes(
    page,
    pageSize,
    typeFilter || undefined
  );

  const columns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 80,
      render: (id: number) => <Link to={`/nodes/${id}`}>{id}</Link>,
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 120,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (title: string | null) => title ?? "—",
    },
    {
      title: "Prior",
      dataIndex: "prior",
      key: "prior",
      width: 80,
    },
    {
      title: "Belief",
      dataIndex: "belief",
      key: "belief",
      width: 80,
      render: (v: number | null) => (v !== null ? v.toFixed(3) : "—"),
    },
    {
      title: "Keywords",
      dataIndex: "keywords",
      key: "keywords",
      width: 200,
      render: (kws: string[]) =>
        kws.slice(0, 3).map((kw) => <Tag key={kw}>{kw}</Tag>),
    },
    {
      title: "Graph",
      key: "graph",
      width: 80,
      render: (_: unknown, record: Node) => (
        <Link to={`/graph?node=${record.id}&hops=1`}>View</Link>
      ),
    },
  ];

  return (
    <>
      <FilterBar selectedType={typeFilter} onTypeChange={setTypeFilter} />
      <Table
        columns={columns}
        dataSource={data?.items}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
          showSizeChanger: true,
          showTotal: (total) => `${total} nodes`,
        }}
        size="small"
      />
    </>
  );
}
