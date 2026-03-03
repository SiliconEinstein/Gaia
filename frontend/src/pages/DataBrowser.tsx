import { useLocation } from "react-router-dom";
import { NodeTable } from "../components/browser/NodeTable";
import { EdgeTable } from "../components/browser/EdgeTable";
import { useQuery } from "@tanstack/react-query";
import { fetchContradictions } from "../api/edges";
import { Table, Tag } from "antd";
import { Link } from "react-router-dom";
import type { HyperEdge } from "../api/types";

function ContradictionTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["contradictions"],
    queryFn: fetchContradictions,
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
      title: "Tail (Side A)",
      dataIndex: "tail",
      key: "tail",
      render: (ids: number[]) =>
        ids.map((id) => (
          <Tag key={id} color="blue">
            <Link to={`/nodes/${id}`}>Node {id}</Link>
          </Tag>
        )),
    },
    {
      title: "Head (Side B)",
      dataIndex: "head",
      key: "head",
      render: (ids: number[]) =>
        ids.map((id) => (
          <Tag key={id} color="red">
            <Link to={`/nodes/${id}`}>Node {id}</Link>
          </Tag>
        )),
    },
    {
      title: "Reasoning",
      dataIndex: "reasoning",
      key: "reasoning",
      width: 80,
      render: (r: unknown[]) => `${r.length} steps`,
    },
    {
      title: "Graph",
      key: "graph",
      width: 80,
      render: (_: unknown, record: HyperEdge) => (
        <Link to={`/graph?node=${record.tail[0]}&hops=1`}>View</Link>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="id"
      loading={isLoading}
      size="small"
    />
  );
}

export function DataBrowser() {
  const location = useLocation();

  if (location.pathname === "/browse/edges") {
    return (
      <div>
        <h2>HyperEdges</h2>
        <EdgeTable />
      </div>
    );
  }

  if (location.pathname === "/browse/contradictions") {
    return (
      <div>
        <h2>Contradictions</h2>
        <ContradictionTable />
      </div>
    );
  }

  return (
    <div>
      <h2>Nodes</h2>
      <NodeTable />
    </div>
  );
}
