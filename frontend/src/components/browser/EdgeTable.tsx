import { useState } from "react";
import { Table, Tag } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchEdges } from "../../api/edges";
import type { HyperEdge } from "../../api/types";

export function EdgeTable() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, isLoading } = useQuery({
    queryKey: ["edges", page, pageSize],
    queryFn: () => fetchEdges(page, pageSize),
  });

  const columns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 80,
      render: (id: number) => <Link to={`/edges/${id}`}>{id}</Link>,
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 120,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: "Premises",
      dataIndex: "premises",
      key: "premises",
      width: 150,
      render: (ids: number[]) =>
        ids.map((id) => (
          <Tag key={id}>
            <Link to={`/nodes/${id}`}>{id}</Link>
          </Tag>
        )),
    },
    {
      title: "Conclusions",
      dataIndex: "conclusions",
      key: "conclusions",
      width: 150,
      render: (ids: number[]) =>
        ids.map((id) => (
          <Tag key={id}>
            <Link to={`/nodes/${id}`}>{id}</Link>
          </Tag>
        )),
    },
    {
      title: "Probability",
      dataIndex: "probability",
      key: "probability",
      width: 100,
      render: (v: number | null) => (v !== null ? v.toFixed(3) : "—"),
    },
    {
      title: "Verified",
      dataIndex: "verified",
      key: "verified",
      width: 80,
      render: (v: boolean) => (
        <Tag color={v ? "green" : "default"}>{v ? "Yes" : "No"}</Tag>
      ),
    },
    {
      title: "Steps",
      dataIndex: "reasoning",
      key: "reasoning",
      width: 60,
      render: (r: unknown[]) => r.length,
    },
  ];

  return (
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
        showTotal: (total) => `${total} edges`,
      }}
      size="small"
    />
  );
}
